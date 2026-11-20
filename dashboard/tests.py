from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from requests import Timeout

from stores.models import Store
from weather.models import WeatherDaily


class RecommendationWeatherTests(TestCase):
    def setUp(self):
        self.store = Store.objects.create(pk=1, name="한빛베이커리", nx=59, ny=126)
        self.target = timezone.localdate() + timedelta(days=1)

    def recommend(self, target=None):
        response = self.client.get(
            "/api/v1/stores/1/recommendations", {"date": (target or self.target).isoformat()}
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["conditions"]

    def forecast_row(self, pop):
        return WeatherDaily.objects.create(
            nx=59, ny=126, date=self.target, pop_max=pop, base_date="20261120", base_time="1700"
        )

    def mock_forecast(self, request_get, *pops):
        items = [
            {"fcstDate": self.target.strftime("%Y%m%d"), "category": "POP", "fcstValue": str(pop)}
            for pop in pops
        ]
        request_get.return_value.json.return_value = {
            "response": {"header": {"resultCode": "00"}, "body": {"items": {"item": items}}}
        }

    @patch("weather.clients.requests.get")
    def test_missing_forecast_is_fetched_saved_and_reused(self, request_get):
        self.mock_forecast(request_get, 30, 70)

        conditions = self.recommend()
        self.assertEqual(conditions["pop"], 70)
        self.assertEqual(conditions["weather_change"], -0.15)
        self.assertEqual(WeatherDaily.objects.get(nx=59, ny=126, date=self.target).pop_max, 70)
        self.assertEqual(self.recommend()["pop"], 70)
        request_get.assert_called_once()
        params = request_get.call_args.kwargs["params"]
        self.assertEqual((params["nx"], params["ny"]), (59, 126))

    @patch("weather.clients.requests.get")
    def test_null_forecast_is_filled_with_zero(self, request_get):
        row = self.forecast_row(None)
        self.mock_forecast(request_get, 0)

        self.assertEqual(self.recommend()["pop"], 0)
        row.refresh_from_db()
        self.assertEqual(row.pop_max, 0)
        self.assertEqual(self.recommend()["pop"], 0)
        request_get.assert_called_once()

    @patch("weather.clients.requests.get", side_effect=Timeout)
    def test_timeout_keeps_recommendation_available(self, request_get):
        with self.assertLogs("weather.services", level="WARNING"):
            conditions = self.recommend()

        self.assertIsNone(conditions["pop"])
        self.assertEqual(conditions["weather_change"], 0.0)
        self.assertFalse(WeatherDaily.objects.exists())
        request_get.assert_called_once()

    @patch("weather.clients.requests.get")
    def test_response_without_pop_does_not_create_forecast(self, request_get):
        self.mock_forecast(request_get)

        self.assertIsNone(self.recommend()["pop"])
        self.assertFalse(WeatherDaily.objects.exists())
        request_get.assert_called_once()

    @patch("weather.clients.requests.get")
    def test_missing_grid_skips_fetch(self, request_get):
        self.store.nx = None
        self.store.save(update_fields=["nx"])

        self.assertIsNone(self.recommend()["pop"])
        request_get.assert_not_called()

    @patch("weather.clients.requests.get")
    def test_date_outside_forecast_window_skips_fetch(self, request_get):
        self.assertIsNone(self.recommend(self.target - timedelta(days=2))["pop"])
        self.assertIsNone(self.recommend(self.target + timedelta(days=3))["pop"])
        request_get.assert_not_called()
