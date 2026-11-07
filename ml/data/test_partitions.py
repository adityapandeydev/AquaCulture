import copy
import unittest

import pandas as pd

from ml.data.partitions import assign_bins, assert_disjoint, map_parents, split_counts


class PartitionTests(unittest.TestCase):
    def policy(self):
        return {'session_id': 'a', 'partitions': [
            {'name': 'train', 'start_utc': '2026-01-01T00:00:00Z', 'end_utc': '2026-01-01T10:00:00Z', 'hours': 10},
            {'name': 'test', 'start_utc': '2026-01-01T10:00:00Z', 'end_utc': '2026-01-01T20:00:00Z', 'hours': 10}]}

    def frame(self):
        return pd.DataFrame({'session_id': 'a', 'available_at': pd.date_range('2026-01-01 01:00', periods=20, freq='h', tz='UTC'),
                             'candidate_eligible': True})

    def test_boundary_bin_ends_belong_to_preceding_period(self):
        bins = assign_bins(self.frame(), self.policy())
        self.assertEqual(bins.partition.value_counts().to_dict(), {'train': 10, 'test': 10})
        self.assertEqual(bins.iloc[9].partition, 'train')
        self.assertEqual(bins.iloc[10].partition, 'test')

    def test_overlapping_or_gapped_periods_fail(self):
        for start in ['2026-01-01T09:00:00Z', '2026-01-01T11:00:00Z']:
            policy = copy.deepcopy(self.policy())
            policy['partitions'][1]['start_utc'] = start
            with self.assertRaises(ValueError):
                assign_bins(self.frame(), policy)

    def test_missing_hours_and_wrong_session_fail_closed(self):
        with self.assertRaises(ValueError):
            assign_bins(self.frame().drop(index=2), self.policy())
        with self.assertRaises(ValueError):
            assign_bins(self.frame().assign(session_id='other'), self.policy())

    def test_histories_and_labels_never_borrow_from_adjacent_partition(self):
        bins = assign_bins(self.frame(), self.policy())
        counts = split_counts(self.frame(), self.frame(), bins, 6, 1)
        self.assertEqual(counts, {'train': 4, 'test': 4})
        self.assertEqual(split_counts(self.frame(), self.frame(), bins, 6, 3), {'train': 2, 'test': 2})

    def test_missing_future_target_reduces_only_its_partition(self):
        bins = assign_bins(self.frame(), self.policy())
        targets = self.frame()
        targets.loc[19, 'candidate_eligible'] = False
        self.assertEqual(split_counts(self.frame(), targets, bins, 6, 1), {'train': 4, 'test': 3})

    def test_shared_parent_or_target_identity_cannot_cross_partitions(self):
        duplicated = pd.DataFrame({'identity': ['same', 'same'], 'partition': ['train', 'test']})
        with self.assertRaises(ValueError):
            assert_disjoint(duplicated, ['identity'])

    def test_raw_half_open_boundary_and_observation_lineage(self):
        bins = assign_bins(self.frame(), self.policy())
        parents = pd.DataFrame({'session_id': ['a'] * 3, 'source_row': [2, 3, 4],
                                'timestamp_utc': pd.to_datetime(['2026-01-01 09:59:59Z', '2026-01-01 10:00:00Z', '2026-01-01 20:00:00Z'])})
        mapped = map_parents(parents, bins, 'a' * 64)
        self.assertEqual(mapped.source_row.tolist(), [2, 3])
        self.assertEqual(mapped.partition.tolist(), ['train', 'test'])
        self.assertTrue(mapped.source_sha256.eq('a' * 64).all())

    def test_outside_period_and_duplicate_hourly_labels_rejected(self):
        with self.assertRaises(ValueError):
            assign_bins(pd.concat([self.frame(), self.frame().iloc[:1]]), self.policy())
        frame = self.frame()
        frame.loc[0, 'available_at'] -= pd.Timedelta(hours=1)
        with self.assertRaises(ValueError):
            assign_bins(frame, self.policy())


if __name__ == '__main__':
    unittest.main()
