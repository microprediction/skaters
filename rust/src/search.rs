//! Adaptive search over the transform tree. Port of src/skaters/search.py.
//!
//! Beam search over the transform grammar: score candidates by cumulative
//! clamped log-likelihood, expand top performers with new transforms
//! (replaying recent history so children join warm), prune losers.
//!
//! Pool entries keep the live skater (an `Sk` value, itself plain data) next
//! to its recipe, so the whole state is serde-serializable. Tie-breaking
//! mirrors Python exactly: expansion order is score descending then pool
//! index descending (the `(score, i)` tuple sort with `reverse=True`), and
//! the pool-cap prune removes the first argmin.

use crate::dist::Dist;
use crate::leaf::Leaf;
use crate::mathx::fsum;
use crate::periodicity::{top_periods, PeriodDetector};
use crate::skater::{conjugate, Sk};
use crate::transform::{
    ar, difference, drift, ema_transform, fractional_difference, garch_default, grouped_ar,
    holt_linear, power_transform, seasonal_difference, standardize, theta, Transform,
};
use serde::{Deserialize, Serialize};
use std::collections::{HashSet, VecDeque};

// ---------------------------------------------------------------------------
// The grammar: available transforms for expansion
// ---------------------------------------------------------------------------

/// How to build one grammar transform (the factory part of Python's
/// `(name, factory, cost)` triples).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum GrammarOp {
    EmaT(f64),
    Diff,
    Std(f64),
    Frac(f64, usize),
    Garch,
    Pow(f64),
    Ar { order: usize, decay: f64 },
    Gar(usize),
    Theta(f64),
    Drift(f64, f64),
    Holt(f64, f64),
    Seas(usize),
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GrammarEntry {
    pub name: String,
    pub op: GrammarOp,
    /// Cost per observation relative to leaf (Python's empirical scale).
    pub cost: f64,
}

fn g(name: &str, op: GrammarOp, cost: f64) -> GrammarEntry {
    GrammarEntry {
        name: name.to_string(),
        op,
        cost,
    }
}

/// The base grammar, in Python's TRANSFORMS order.
pub fn base_transforms() -> Vec<GrammarEntry> {
    vec![
        g("ema_t(0.05)", GrammarOp::EmaT(0.05), 1.0),
        g("ema_t(0.1)", GrammarOp::EmaT(0.1), 1.0),
        g("ema_t(0.3)", GrammarOp::EmaT(0.3), 1.0),
        g("diff", GrammarOp::Diff, 1.0),
        g("std(0.05)", GrammarOp::Std(0.05), 1.0),
        g("frac(0.3)", GrammarOp::Frac(0.3, 30), 3.0),
        g("garch", GrammarOp::Garch, 1.0),
        g("pow(0.5)", GrammarOp::Pow(0.5), 1.0),
        g(
            "ar(2)",
            GrammarOp::Ar {
                order: 2,
                decay: 0.0,
            },
            2.0,
        ),
        g(
            "ar(5)",
            GrammarOp::Ar {
                order: 5,
                decay: 1.0,
            },
            3.0,
        ),
        g("gar(16)", GrammarOp::Gar(16), 2.0),
        g("theta(0.1)", GrammarOp::Theta(0.1), 1.0),
        g("theta(0.3)", GrammarOp::Theta(0.3), 1.0),
        g("drift", GrammarOp::Drift(0.002, 0.001), 1.0),
        g("drift(0.01)", GrammarOp::Drift(0.01, 0.002), 1.0),
        g("holt(0.1,0.05)", GrammarOp::Holt(0.1, 0.05), 1.0),
        g("holt(0.3,0.1)", GrammarOp::Holt(0.3, 0.1), 1.0),
        g("seas(7)", GrammarOp::Seas(7), 1.0),
        g("seas(12)", GrammarOp::Seas(12), 1.0),
        g("seas(24)", GrammarOp::Seas(24), 1.0),
    ]
}

fn make_transform(op: &GrammarOp) -> Transform {
    match *op {
        GrammarOp::EmaT(a) => ema_transform(a),
        GrammarOp::Diff => difference(),
        GrammarOp::Std(a) => standardize(a, 1e-8),
        GrammarOp::Frac(d, w) => fractional_difference(d, w),
        GrammarOp::Garch => garch_default(),
        GrammarOp::Pow(p) => power_transform(p),
        GrammarOp::Ar { order, decay } => ar(order, 0.99, 1.0, decay),
        GrammarOp::Gar(m) => grouped_ar(m, 0.99, 1.0),
        GrammarOp::Theta(a) => theta(a),
        GrammarOp::Drift(a, s) => drift(a, s),
        GrammarOp::Holt(a, b) => holt_linear(a, b),
        GrammarOp::Seas(p) => seasonal_difference(p),
    }
}

// ---------------------------------------------------------------------------
// Pool entries
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SearchEntry {
    pub sk: Sk,
    pub depth: usize,
    /// Transform names, innermost first (for building children).
    pub recipe: Vec<String>,
    /// Total cost per observation (leaf + transforms).
    pub cost: f64,
    pub age: u64,
    /// Becomes true after warmup/initial burn-in.
    pub warmed: bool,
    pub log_w: Vec<f64>,
    pub queues: Vec<VecDeque<Dist>>,
    /// Latest per-horizon predictions (empty until first run: Python's None).
    pub dists: Vec<Dist>,
}

fn make_entry(sk: Sk, depth: usize, recipe: Vec<String>, k: usize, cost: f64) -> SearchEntry {
    SearchEntry {
        sk,
        depth,
        recipe,
        cost,
        age: 0,
        warmed: false,
        log_w: vec![0.0; k],
        queues: vec![VecDeque::new(); k],
        dists: Vec::new(),
    }
}

fn build_from_recipe(recipe: &[String], k: usize, transforms: &[GrammarEntry]) -> Sk {
    let mut f = Sk::Leaf(Leaf::new(k));
    for t_name in recipe {
        // Python's dict lookup: last entry with this name wins.
        let op = transforms
            .iter()
            .rev()
            .find(|t| &t.name == t_name)
            .map(|t| &t.op)
            .expect("recipe names a transform absent from the grammar");
        f = conjugate(f, make_transform(op), k);
    }
    f
}

fn avg_log_w(e: &SearchEntry, k: usize) -> f64 {
    fsum(e.log_w.iter().copied()) / k as f64
}

// ---------------------------------------------------------------------------
// The search skater
// ---------------------------------------------------------------------------

/// Adaptive-search skater. Construct with [`search`], tweak public knobs
/// before the first step if needed (the pool seeds lazily, as in Python).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Search {
    pub k: usize,
    pub learning_rate: f64,
    pub complexity_penalty: f64,
    pub max_pool: usize,
    pub expand_interval: u64,
    pub expand_top_n: usize,
    pub max_depth: usize,
    pub replay_buffer: usize,
    pub prune_threshold: f64,
    pub max_components: usize,
    /// Maximum per-candidate cost; `f64::INFINITY` means no limit. JSON has
    /// no Infinity, so it round-trips as null via the adapter below.
    #[serde(with = "budget_serde")]
    pub cost_budget: f64,
    pub pool: Vec<SearchEntry>,
    pub n_obs: u64,
    pub buffer: VecDeque<f64>,
    pub pd: PeriodDetector,
    pub detected_periods: Vec<usize>,
    /// Per-instance grammar: base transforms plus injected seasonals.
    pub transforms: Vec<GrammarEntry>,
}

/// Serialize a possibly-infinite budget as `Option<f64>` (null = no limit),
/// since JSON rejects Infinity.
mod budget_serde {
    use serde::{Deserialize, Deserializer, Serializer};

    pub fn serialize<S: Serializer>(v: &f64, s: S) -> Result<S::Ok, S::Error> {
        if v.is_finite() {
            s.serialize_some(v)
        } else {
            s.serialize_none()
        }
    }

    pub fn deserialize<'de, D: Deserializer<'de>>(d: D) -> Result<f64, D::Error> {
        Ok(Option::<f64>::deserialize(d)?.unwrap_or(f64::INFINITY))
    }
}

/// Python `search(k)` defaults.
pub fn search(k: usize) -> Search {
    Search {
        k,
        learning_rate: 0.5,
        complexity_penalty: 0.02,
        max_pool: 30,
        expand_interval: 100,
        expand_top_n: 3,
        max_depth: 3,
        replay_buffer: 500,
        prune_threshold: -50.0,
        max_components: 20,
        cost_budget: f64::INFINITY,
        pool: Vec::new(),
        n_obs: 0,
        buffer: VecDeque::new(),
        pd: PeriodDetector::new(),
        detected_periods: Vec::new(),
        transforms: base_transforms(),
    }
}

fn init_pool(k: usize, cost_budget: f64) -> Vec<SearchEntry> {
    let mut pool = Vec::new();

    // Depth 0: just a leaf (cost = 1 for the leaf itself)
    let mut e = make_entry(Sk::Leaf(Leaf::new(k)), 0, Vec::new(), k, 1.0);
    e.warmed = true;
    pool.push(e);

    // Depth 1: each single transform applied to leaf
    for t in base_transforms() {
        let candidate_cost = 1.0 + t.cost;
        if candidate_cost > cost_budget {
            continue;
        }
        let sk = conjugate(Sk::Leaf(Leaf::new(k)), make_transform(&t.op), k);
        let mut e = make_entry(sk, 1, vec![t.name.clone()], k, candidate_cost);
        e.warmed = true;
        pool.push(e);
    }
    pool
}

fn expand(
    pool: &[SearchEntry],
    k: usize,
    top_n: usize,
    max_depth: usize,
    transforms: &[GrammarEntry],
    cost_budget: f64,
) -> Vec<SearchEntry> {
    let scores: Vec<f64> = pool.iter().map(|e| avg_log_w(e, k)).collect();
    // Python: sort (score, index) tuples reverse=True — score desc, index desc.
    let mut order: Vec<usize> = (0..pool.len()).collect();
    order.sort_by(|&a, &b| {
        scores[b]
            .partial_cmp(&scores[a])
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(b.cmp(&a))
    });

    let mut existing: HashSet<Vec<String>> =
        pool.iter().map(|e| e.recipe.clone()).collect();

    let mut children = Vec::new();
    for &pi in order.iter().take(top_n) {
        let parent = &pool[pi];
        if parent.depth >= max_depth {
            continue;
        }
        for t in transforms {
            // Check cost budget
            let child_cost = parent.cost + t.cost;
            if child_cost > cost_budget {
                continue;
            }
            if parent.recipe.last() == Some(&t.name) {
                continue;
            }
            let mut new_recipe = parent.recipe.clone();
            new_recipe.push(t.name.clone());
            if existing.contains(&new_recipe) {
                continue;
            }
            existing.insert(new_recipe.clone());

            let sk = build_from_recipe(&new_recipe, k, transforms);
            let depth = new_recipe.len();
            children.push(make_entry(sk, depth, new_recipe, k, child_cost));
        }
    }
    children
}

/// Replay the history buffer through a candidate so it joins warm: no
/// scoring, just state building; the last prediction is queued for scoring
/// on the next real observation.
fn warmup(entry: &mut SearchEntry, buffer: &VecDeque<f64>, k: usize) {
    for &y in buffer {
        entry.dists = entry.sk.step(y);
        entry.age += 1;
    }
    if !entry.dists.is_empty() {
        for h in 0..k {
            entry.queues[h].clear();
            entry.queues[h].push_back(entry.dists[h].clone());
        }
    }
    entry.warmed = true;
}

/// Remove candidates hopelessly behind the leader, then cap the pool by
/// dropping the first argmin repeatedly (Python's `min(range(...))`).
fn prune(pool: &mut Vec<SearchEntry>, threshold: f64, max_pool: usize, k: usize) {
    if pool.len() <= 1 {
        return;
    }
    let best = pool
        .iter()
        .map(|e| avg_log_w(e, k))
        .fold(f64::NEG_INFINITY, f64::max);

    let mut i = 0;
    while i < pool.len() {
        if avg_log_w(&pool[i], k) < best + threshold && pool.len() > 1 {
            pool.remove(i);
        } else {
            i += 1;
        }
    }

    while pool.len() > max_pool {
        let mut worst = 0;
        let mut worst_v = f64::INFINITY;
        for (j, e) in pool.iter().enumerate() {
            let v = avg_log_w(e, k);
            if v < worst_v {
                worst_v = v;
                worst = j;
            }
        }
        pool.remove(worst);
    }
}

impl Search {
    pub fn step(&mut self, y: f64) -> Vec<Dist> {
        let k = self.k;
        if self.n_obs == 0 {
            self.pool = init_pool(k, self.cost_budget);
        }
        self.n_obs += 1;
        self.buffer.push_back(y);
        if self.buffer.len() > self.replay_buffer {
            self.buffer.pop_front();
        }

        // 1. Run all active candidates
        for e in self.pool.iter_mut() {
            e.dists = e.sk.step(y);
            e.age += 1;
        }

        // 2+3. Queue current predictions, then resolve the ones that have
        // matured. Horizon h (0-based) is (h+1)-step-ahead, so the Dist
        // issued h+1 steps ago is the one that targeted the current y.
        for e in self.pool.iter_mut() {
            for h in 0..k {
                let q = &mut e.queues[h];
                q.push_back(e.dists[h].clone());
                if q.len() > h + 1 {
                    let past = q.pop_front().unwrap();
                    if e.warmed {
                        let mut lp = past.logpdf(y);
                        // Bounded loss: clamp both tails so neither -inf nor
                        // a +inf (exact hit on a Dirac atom) can dominate or
                        // NaN-poison the log-weight; `!(lp >= -20)` also
                        // catches NaN.
                        if lp > 20.0 {
                            lp = 20.0;
                        } else if !(lp >= -20.0) {
                            lp = -20.0;
                        }
                        e.log_w[h] += self.learning_rate * lp
                            - self.complexity_penalty * e.depth as f64;
                    }
                }
            }
        }

        // 3b. Run period detector
        let scores = self.pd.step(y);

        // 4. Periodically expand and prune
        if self.n_obs % self.expand_interval == 0 && self.n_obs > 10 {
            // Inject seasonal transforms for newly detected periods
            let detected = top_periods(&scores, 0.3, 3);
            for period in detected {
                if !self.detected_periods.contains(&period) {
                    self.detected_periods.push(period);
                    self.transforms.push(GrammarEntry {
                        name: format!("seas({period})"),
                        op: GrammarOp::Seas(period),
                        cost: 2.0,
                    });
                }
            }

            let mut new_children = expand(
                &self.pool,
                k,
                self.expand_top_n,
                self.max_depth,
                &self.transforms,
                self.cost_budget,
            );
            // Replay history through new children so they join warm
            for child in new_children.iter_mut() {
                warmup(child, &self.buffer, k);
            }
            self.pool.append(&mut new_children);
            prune(&mut self.pool, self.prune_threshold, self.max_pool, k);
        }

        // 5. Combine predictions via softmax weights
        let n = self.pool.len();
        let mut combined = Vec::with_capacity(k);
        for h in 0..k {
            let log_ws: Vec<f64> = self.pool.iter().map(|e| e.log_w[h]).collect();
            let max_lw = log_ws.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
            let weights: Vec<f64> = if max_lw.is_finite() {
                log_ws.iter().map(|&lw| libm::exp(lw - max_lw)).collect()
            } else {
                vec![1.0; n]
            };

            let horizon: Vec<&Dist> = self.pool.iter().map(|e| &e.dists[h]).collect();
            let mut dist = Dist::combine_refs(&horizon, Some(&weights));
            if dist.len() > self.max_components {
                dist = dist.prune(self.max_components);
            }
            combined.push(dist);
        }
        combined
    }
}
