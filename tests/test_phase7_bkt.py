from django.test import SimpleTestCase

from apps.adaptive.bkt import (
    BKTParameters,
    mastery_band,
    update_mastery,
    update_mastery_for_session,
)


class PureBKTTests(SimpleTestCase):
    def setUp(self):
        self.parameters = BKTParameters()

    def test_correct_answer_matches_hand_computed_value(self):
        result = update_mastery(
            0.30,
            True,
            self.parameters.p_t,
            self.parameters.p_g,
            self.parameters.p_s,
        )
        self.assertAlmostEqual(
            result.p_after_observation,
            0.7959183673469388,
            delta=1e-12,
        )
        self.assertAlmostEqual(
            result.p_after_learning,
            0.8142857142857143,
            delta=1e-12,
        )
        self.assertTrue(result.learning_transition_applied)

    def test_incorrect_answer_matches_formula(self):
        result = update_mastery(0.30, False, 0.09, 0.10, 0.09)
        expected_posterior = (0.30 * 0.09) / (
            0.30 * 0.09 + (1 - 0.30) * (1 - 0.10)
        )
        expected_after_learning = expected_posterior + (
            1 - expected_posterior
        ) * 0.09
        self.assertAlmostEqual(
            result.p_after_observation,
            expected_posterior,
            delta=1e-12,
        )
        self.assertAlmostEqual(
            result.p_after_learning,
            expected_after_learning,
            delta=1e-12,
        )

    def test_hinted_foundational_skips_posterior(self):
        result = update_mastery_for_session(
            0.30,
            True,
            0.09,
            0.10,
            0.09,
            session_type="foundational",
            hint_used=True,
        )
        self.assertIsNone(result.p_after_observation)
        self.assertAlmostEqual(result.p_after_learning, 0.363, delta=1e-12)
        self.assertTrue(result.learning_transition_applied)

    def test_pretest_applies_posterior_without_learning_transition(self):
        result = update_mastery_for_session(
            0.30,
            True,
            0.09,
            0.10,
            0.09,
            session_type="pretest",
        )
        self.assertAlmostEqual(
            result.p_after_learning,
            result.p_after_observation,
            delta=1e-12,
        )
        self.assertFalse(result.learning_transition_applied)

    def test_posttest_is_rejected_by_engine(self):
        with self.assertRaisesMessage(ValueError, "must never be processed"):
            update_mastery_for_session(
                0.30,
                True,
                0.09,
                0.10,
                0.09,
                session_type="posttest",
            )

    def test_valid_inputs_produce_bounded_results(self):
        for p in (0.0, 0.30, 0.50, 0.80, 1.0):
            for is_correct in (False, True):
                with self.subTest(p=p, is_correct=is_correct):
                    result = update_mastery(p, is_correct, 0.09, 0.10, 0.09)
                    self.assertGreaterEqual(result.p_after_learning, 0.0)
                    self.assertLessEqual(result.p_after_learning, 1.0)

    def test_zero_denominator_is_rejected_with_inputs(self):
        with self.assertRaisesMessage(ValueError, "denominator is zero") as error:
            update_mastery(0.0, True, 0.09, 0.0, 0.09)
        self.assertIn("inputs=", str(error.exception))

    def test_mastery_bands_use_exact_boundaries(self):
        self.assertEqual(mastery_band(0.0), "np")
        self.assertEqual(mastery_band(0.499999), "np")
        self.assertEqual(mastery_band(0.50), "dev")
        self.assertEqual(mastery_band(0.799999), "dev")
        self.assertEqual(mastery_band(0.80), "strong")
        self.assertEqual(mastery_band(1.0), "strong")
