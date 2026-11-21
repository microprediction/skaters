// Conjugation — JS port of skaters/conjugate.py.
//
// Given an invertible transform T = {forward, inverseK} and a skater f,
// produce a new skater that transforms each observation, predicts in the
// transformed space, and inverts the predictions back.

export function conjugate(skater, transform, k = 1) {
  const { forward, inverseK } = transform;

  function _conjugated(y, state) {
    if (state === null || state === undefined) {
      state = { t_state: null, s_state: null };
    }
    const [yPrime, tState] = forward(y, state.t_state);
    state.t_state = tState;
    const [distsPrime, sState] = skater(yPrime, state.s_state);
    state.s_state = sState;
    const dists = inverseK(distsPrime, state.t_state);
    return [dists, state];
  }
  _conjugated.skaterName = `conjugate(${skater.skaterName || "?"})`;
  return _conjugated;
}
