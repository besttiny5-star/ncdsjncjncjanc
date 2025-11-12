import unittest

from payment_qa_bot.services.payload import parse_payload


class PayloadParsingTests(unittest.TestCase):
    def test_calc_v1_payload_accepts_manual_tests_count(self):
        payload = "calc_v1_geoIN_tests7_payoutN_method<UVBJTkQ>_price595"
        result = parse_payload(payload)

        self.assertTrue(result.ok)
        self.assertEqual(result.data.geo, "IN")
        self.assertEqual(result.data.tests_count, 7)
        self.assertEqual(result.data.price_total, 595)

    def test_calc_v1_payload_rejects_out_of_range_tests_count(self):
        payload = "calc_v1_geoIN_tests42_payoutW_price3600"
        result = parse_payload(payload)

        self.assertTrue(result.ok)
        self.assertIsNone(result.data.tests_count)
        self.assertTrue(result.data.withdraw_required)

    def test_reference_payload_reports_token(self):
        result = parse_payload("calc_ref_abcd1234")

        self.assertFalse(result.ok)
        self.assertEqual(result.data.reference_token, "abcd1234")
        self.assertEqual(result.error, "payload_reference")


if __name__ == "__main__":
    unittest.main()
