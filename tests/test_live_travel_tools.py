import unittest

from app import convert_currency, get_weather_for_city


class LiveTravelToolsTests(unittest.TestCase):
    def test_weather_tool_returns_summary(self):
        result = get_weather_for_city("Singapore")

        self.assertIn("city", result)
        self.assertIn("weather_summary", result)
        self.assertIn("forecast_days", result)
        self.assertGreater(len(result["forecast_days"]), 0)

    def test_currency_tool_returns_conversion(self):
        result = convert_currency(50000, "INR", "SGD")

        self.assertEqual(result["from_currency"], "INR")
        self.assertEqual(result["to_currency"], "SGD")
        self.assertGreater(result["converted_amount"], 0)


if __name__ == "__main__":
    unittest.main()
