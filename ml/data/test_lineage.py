import unittest

import pandas as pd

from ml.data.lineage import overlap_evidence, validate_partition_claim


class LineageTests(unittest.TestCase):
    def test_overlap_keeps_multiplicity_separate_from_unique_vectors(self):
        left = pd.DataFrame({"do": [5., 5., 6.]})
        right = pd.DataFrame({"do": [5., 6., 7.]})
        result = overlap_evidence(left, right, ["do"])
        self.assertEqual(result["shared_unique_vectors"], 2)
        self.assertEqual(result["shared_rows_multiset"], 2)
        self.assertEqual(result["left_rows"], 3)

    def test_shared_study_cannot_be_claimed_as_independent_site(self):
        with self.assertRaises(ValueError):
            validate_partition_claim({"study_a"}, {"study_a"}, "independent_site")

    def test_chronological_claim_does_not_require_separate_studies(self):
        validate_partition_claim({"study_a"}, {"study_a"}, "chronological_within_study")
        # Target disjointness and timing are separate mandatory checks.


if __name__ == "__main__":
    unittest.main()
