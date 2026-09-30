"""P1-1 HMM稳态诊断师 - 两状态隐马尔可夫模型"""
import numpy as np
import pandas as pd


class SteadyStateDiagnostician:
    """两状态HMM：稳态/非稳态，输出状态转移概率与预期持续时间"""

    def __init__(self, n_states=2, lookback=252):
        self.n_states = n_states
        self.lookback = lookback
        self.transition_matrix = None
        self.state_means = None
        self.state_stds = None
        self.current_state_probs = None

    def _gaussian_pdf(self, x, mu, sigma):
        if sigma == 0:
            return 1.0 if x == mu else 0.0
        return np.exp(-0.5 * ((x - mu) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi))

    def _estimate_emission(self, mk_vals, states):
        means, stds = [], []
        for s in range(self.n_states):
            mask = states == s
            if mask.sum() > 0:
                means.append(mk_vals[mask].mean())
                stds.append(mk_vals[mask].std())
            else:
                means.append(0.5)
                stds.append(0.1)
        return np.array(means), np.array(stds)

    def _estimate_transition(self, states):
        trans = np.zeros((self.n_states, self.n_states))
        for i in range(1, len(states)):
            trans[states[i - 1], states[i]] += 1
        row_sums = trans.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1
        return trans / row_sums

    def _viterbi(self, obs, means, stds, trans_mat, start_prob):
        T = len(obs)
        N = self.n_states
        delta = np.zeros((T, N))
        psi = np.zeros((T, N), dtype=int)
        for i in range(N):
            delta[0, i] = start_prob[i] * self._gaussian_pdf(obs[0], means[i], stds[i])
        for t in range(1, T):
            for j in range(N):
                prob = delta[t - 1, :] * trans_mat[:, j]
                psi[t, j] = np.argmax(prob)
                delta[t, j] = np.max(prob) * self._gaussian_pdf(obs[t], means[j], stds[j])
        states = np.zeros(T, dtype=int)
        states[-1] = np.argmax(delta[-1, :])
        for t in range(T - 2, -1, -1):
            states[t] = psi[t + 1, states[t + 1]]
        return states

    def fit(self, mk_series):
        mk_vals = mk_series.values if isinstance(mk_series, pd.Series) else np.array(mk_series)
        if len(mk_vals) < 60:
            return False
        threshold = np.percentile(mk_vals, 60)
        states = (mk_vals > threshold).astype(int)
        for _ in range(3):
            means, stds = self._estimate_emission(mk_vals, states)
            trans_mat = self._estimate_transition(states)
            states = self._viterbi(mk_vals, means, stds, trans_mat, np.array([0.7, 0.3]))
        self.transition_matrix = trans_mat
        self.state_means = means
        self.state_stds = stds
        last_obs = mk_vals[-1]
        state_probs = np.array([self._gaussian_pdf(last_obs, means[i], stds[i]) for i in range(self.n_states)])
        self.current_state_probs = state_probs / state_probs.sum()
        return True

    def get_diagnosis(self):
        if self.transition_matrix is None:
            return None
        current_state = np.argmax(self.current_state_probs)
        state_names = ['稳态', '非稳态']
        durations = []
        for i in range(self.n_states):
            p = self.transition_matrix[i, i]
            durations.append(1 / (1 - p) if p < 1 else float('inf'))
        p_stay = self.transition_matrix[current_state, current_state] ** 20
        return {
            'current_state': state_names[current_state],
            'current_confidence': round(self.current_state_probs[current_state], 4),
            'expected_duration_days': round(durations[current_state], 1),
            'stay_prob_20d': round(p_stay, 4),
            'switch_prob_20d': round(1 - p_stay, 4),
            'transition_matrix': self.transition_matrix.tolist()
        }
