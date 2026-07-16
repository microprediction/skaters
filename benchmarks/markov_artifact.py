import math
import random


class Forecaster:
    def __init__(self):
        """No arguments. All state internal."""
        # ---- counters ----
        self.n = 0
        self.prev_y = None

        # ---- ExponentialSmoothing (mean) ----
        self.alpha_es = 0.08
        self.level = 0.0

        # ---- AutoRegression via RLS ----
        self.p = 3
        self.dim = self.p + 1          # bias + p lags
        self.theta = [0.0] * self.dim
        self.P = [[ (1000.0 if i == j else 0.0) for j in range(self.dim)]
                  for i in range(self.dim)]
        self.lam = 0.995               # forgetting factor
        self.history = []              # recent observations (most recent last)

        # ---- scale models ----
        self.var_g = 1.0               # GARCH conditional variance
        self.var_es = 1.0              # ES-smoothed residual variance
        self.lr = 1.0                  # long-run robust variance
        self.a = 0.08                  # GARCH ARCH weight
        self.b = 0.90                  # GARCH persistence
        self.beta = 0.04               # ES scale smoothing
        self.lr_decay = 0.995

        # ---- Student tails ----
        self.nu = 6.0
        self.e2 = 1.0                  # EWMA of standardized sq err
        self.e4 = 3.0                  # EWMA of standardized 4th err

        # ---- RegimeWatcher ----
        self.mstat = 1.0               # EWMA of standardized squared error
        self.reg_gamma = 0.92
        self.reg_thresh = 3.5
        self.inflation = 1.0
        self.cooldown = 0

        # ---- adaptive blend weights ----
        self.decay = 0.97
        self.cum_m = [0.0, 0.0]        # ES, AR log-scores
        self.cum_s = [0.0, 0.0]        # GARCH, ES-var log-scores

        self.floor = 1e-8

    # ----------------------------------------------------------
    def _softmax2(self, c):
        m = max(c)
        e0 = math.exp(min(50.0, c[0] - m))
        e1 = math.exp(min(50.0, c[1] - m))
        s = e0 + e1
        if s <= 0 or not math.isfinite(s):
            return [0.5, 0.5]
        return [e0 / s, e1 / s]

    def _ar_features(self):
        # returns feature vector x = [1, y_{t-1}, ..., y_{t-p}] if available
        if len(self.history) < self.p:
            return None
        x = [1.0]
        for k in range(1, self.p + 1):
            x.append(self.history[-k])
        return x

    def _dot(self, a, b):
        s = 0.0
        for i in range(len(a)):
            s += a[i] * b[i]
        return s

    def _predict(self):
        # mean components
        mu_es = self.level
        x = self._ar_features()
        if x is not None:
            mu_ar = self._dot(self.theta, x)
            if not math.isfinite(mu_ar):
                mu_ar = mu_es
        else:
            mu_ar = mu_es

        wm = self._softmax2(self.cum_m)
        mu = wm[0] * mu_es + wm[1] * mu_ar

        # scale components
        var_g = max(self.var_g, self.floor)
        var_es = max(self.var_es, self.floor)
        ws = self._softmax2(self.cum_s)
        base_var = ws[0] * var_g + ws[1] * var_es
        base_var = max(base_var, self.floor)

        var = base_var * self.inflation
        var = max(var, self.floor)

        nu = self.nu
        return {
            'mu': mu, 'var': var, 'base_var': base_var,
            'mu_es': mu_es, 'mu_ar': mu_ar,
            'var_g': var_g, 'var_es': var_es,
            'nu': nu, 'x': x
        }

    @staticmethod
    def _t_logpdf(y, mu, var, nu):
        var = max(var, 1e-12)
        if nu <= 2.5:
            nu = 2.5
        s2 = var * (nu - 2.0) / nu
        s2 = max(s2, 1e-12)
        s = math.sqrt(s2)
        z = (y - mu) / s
        val = (math.lgamma((nu + 1.0) / 2.0)
               - math.lgamma(nu / 2.0)
               - 0.5 * math.log(nu * math.pi)
               - math.log(s)
               - (nu + 1.0) / 2.0 * math.log(1.0 + z * z / nu))
        if not math.isfinite(val):
            return -50.0
        return val

    # ----------------------------------------------------------
    def logpdf(self, y):
        if self.n == 0:
            # no information yet: broad default
            val = self._t_logpdf(y, 0.0, 1.0, self.nu)
            return val if math.isfinite(val) else -50.0
        pr = self._predict()
        val = self._t_logpdf(y, pr['mu'], pr['var'], pr['nu'])
        if not math.isfinite(val):
            val = -50.0
        return val

    # ----------------------------------------------------------
    def update(self, y):
        # first observation: bootstrap
        if self.n == 0:
            self.level = y
            self.history.append(y)
            self.prev_y = y
            self.n = 1
            return

        pr = self._predict()
        mu = pr['mu']
        var = pr['var']
        base_var = pr['base_var']
        nu = pr['nu']
        x = pr['x']

        # residual under blended prediction
        r = y - mu

        # ---- update adaptive blend weights via component log-scores ----
        s_es = self._t_logpdf(y, pr['mu_es'], var, nu)
        s_ar = self._t_logpdf(y, pr['mu_ar'], var, nu)
        self.cum_m[0] = self.decay * self.cum_m[0] + s_es
        self.cum_m[1] = self.decay * self.cum_m[1] + s_ar

        s_g = self._t_logpdf(y, mu, pr['var_g'] * self.inflation, nu)
        s_e = self._t_logpdf(y, mu, pr['var_es'] * self.inflation, nu)
        self.cum_s[0] = self.decay * self.cum_s[0] + s_g
        self.cum_s[1] = self.decay * self.cum_s[1] + s_e

        # keep cumulative scores bounded
        for arr in (self.cum_m, self.cum_s):
            m = max(arr)
            arr[0] -= m
            arr[1] -= m

        # ---- robust squared surprise (outlier clipped) ----
        cap = 20.0 * max(base_var, self.floor)
        r2 = r * r
        r2c = r2 if r2 < cap else cap

        # standardized error for regime + tail estimation
        e = r / math.sqrt(max(var, self.floor))
        e_sq = min(e * e, 50.0)

        # ---- RegimeWatcher: monitor for structural break ----
        self.mstat = self.reg_gamma * self.mstat + (1.0 - self.reg_gamma) * e_sq
        break_detected = False
        if self.cooldown > 0:
            self.cooldown -= 1
        if self.mstat > self.reg_thresh and self.cooldown == 0 and self.n > 5:
            break_detected = True

        # ---- update Student-t degrees of freedom (heavy tails) ----
        self.e2 = 0.98 * self.e2 + 0.02 * e_sq
        self.e4 = 0.98 * self.e4 + 0.02 * min(e_sq * e_sq, 200.0)
        denom = max(self.e2 * self.e2, 1e-6)
        kurt = self.e4 / denom
        if kurt > 3.05:
            nu_new = 4.0 + 6.0 / (kurt - 3.0)
        else:
            nu_new = 40.0
        nu_new = max(3.0, min(50.0, nu_new))
        self.nu = 0.97 * self.nu + 0.03 * nu_new

        # ---- update scale models (feed the density next step) ----
        omega = max(0.0, (1.0 - self.a - self.b)) * max(self.lr, self.floor)
        self.var_g = omega + self.a * r2c + self.b * self.var_g
        self.var_g = max(self.var_g, self.floor)

        self.var_es = self.beta * r2c + (1.0 - self.beta) * self.var_es
        self.var_es = max(self.var_es, self.floor)

        self.lr = self.lr_decay * self.lr + (1.0 - self.lr_decay) * r2c
        self.lr = max(self.lr, self.floor)

        # ---- update mean models ----
        # ExponentialSmoothing level
        self.level = self.alpha_es * y + (1.0 - self.alpha_es) * self.level

        # AutoRegression RLS update (only if we had features)
        if x is not None:
            # Px = P x
            Px = [0.0] * self.dim
            for i in range(self.dim):
                s = 0.0
                Pi = self.P[i]
                for j in range(self.dim):
                    s += Pi[j] * x[j]
                Px[i] = s
            xPx = 0.0
            for j in range(self.dim):
                xPx += x[j] * Px[j]
            denomk = self.lam + xPx
            if denomk <= 0 or not math.isfinite(denomk):
                denomk = 1e-6
            k = [Px[i] / denomk for i in range(self.dim)]
            err = y - self._dot(self.theta, x)
            for i in range(self.dim):
                self.theta[i] += k[i] * err
            # P = (P - k Px^T)/lam
            for i in range(self.dim):
                ki = k[i]
                Pi = self.P[i]
                for j in range(self.dim):
                    Pi[j] = (Pi[j] - ki * Px[j]) / self.lam

        # ---- regime break handling: inflate variance & refresh ----
        if break_detected:
            self.inflation = 5.0
            # refresh scale toward the fresh surprise
            self.var_g = max(self.var_g, r2c)
            self.var_es = max(self.var_es, r2c)
            # nudge mean level toward the new observation
            self.level = 0.5 * self.level + 0.5 * y
            # reset AR covariance to allow fast re-learning
            for i in range(self.dim):
                for j in range(self.dim):
                    self.P[i][j] = 1000.0 if i == j else 0.0
            # give the blend a fresh start (mild)
            self.cum_m = [0.0, 0.0]
            self.cum_s = [0.0, 0.0]
            self.mstat = 1.0
            self.cooldown = 10
        else:
            # inflation decays back toward 1
            self.inflation = 1.0 + (self.inflation - 1.0) * 0.8
            if self.inflation < 1.0:
                self.inflation = 1.0

        # ---- bookkeeping ----
        self.history.append(y)
        if len(self.history) > self.p + 2:
            self.history = self.history[-(self.p + 2):]
        self.prev_y = y
        self.n += 1