import unittest

import pandas as pd

from ml.data.eligibility import count_examples


class EligibilityTests(unittest.TestCase):
    def frame(self, n=10, session='a'):
        return pd.DataFrame({'session_id': session,
                             'available_at': pd.date_range('2026-01-01 01:00', periods=n, freq='h', tz='UTC'),
                             'candidate_eligible': True})

    def test_history_includes_issue_hour_and_target_is_future(self):
        frame = self.frame()
        self.assertEqual(count_examples(frame, frame, 6, 1), {'a': 4})
        self.assertEqual(count_examples(frame, frame, 6, 3), {'a': 2})
        self.assertEqual(count_examples(frame, frame, 10, 1), {'a': 0})

    def test_sessions_cannot_supply_each_others_history(self):
        frame = pd.concat([self.frame(5), self.frame(5, 'b')])
        self.assertEqual(count_examples(frame, frame, 6, 1), {'a': 0, 'b': 0})

    def test_missing_required_input_and_target_reduce_counts(self):
        inputs = self.frame()
        targets = self.frame()
        inputs.loc[0, 'candidate_eligible'] = False
        self.assertEqual(count_examples(inputs, targets, 6, 1), {'a': 3})
        targets.loc[9, 'candidate_eligible'] = False
        self.assertEqual(count_examples(inputs, targets, 6, 1), {'a': 2})

    def test_missing_future_do_path_does_not_get_bridged(self):
        frame = self.frame()
        targets = frame.drop(index=7)
        self.assertEqual(count_examples(frame, targets, 6, 3), {'a': 0})

    def test_future_optional_sensors_not_required(self):
        inputs = self.frame()
        inputs.loc[6:, 'candidate_eligible'] = False
        self.assertEqual(count_examples(inputs, self.frame(), 6, 3), {'a': 1})

    def test_duplicate_keys_and_invalid_durations_rejected(self):
        frame = self.frame()
        with self.assertRaises(ValueError):
            count_examples(pd.concat([frame, frame]), frame, 6, 1)
        with self.assertRaises(ValueError):
            count_examples(frame, frame, 0, 1)


if __name__ == '__main__':
    unittest.main()
