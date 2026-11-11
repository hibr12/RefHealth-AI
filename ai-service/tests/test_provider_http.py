"""Provider failure recovery without real requests, sleeps, secrets or model changes."""
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

import httpx

from corecare import provider_http as transport


class ProviderTransportTests(unittest.TestCase):
    def request(self):
        return Request("https://provider.example/chat", data=b'{"question":"synthetic"}',
                       headers={"Content-Type": "application/json", "Authorization": "Bearer test-secret"})

    def test_connection_timeouts_retry_then_succeed_without_logging_secrets(self):
        calls = []

        def handle(request):
            calls.append(request)
            if len(calls) < 3:
                raise httpx.ConnectTimeout("test-secret must not be logged")
            return httpx.Response(200, json={"ok": True})

        with httpx.Client(transport=httpx.MockTransport(handle)) as client, \
                patch.object(transport, "_get_client", return_value=client), \
                patch.object(transport, "sleep") as sleep, \
                self.assertLogs(transport.logger, level="WARNING") as logs:
            with transport.open_provider_response(self.request()) as response:
                self.assertIn(b'"ok":true', response.read())
        self.assertEqual(len(calls), 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.5, 1.0])
        self.assertTrue(all(request.headers["Authorization"] == "Bearer test-secret" for request in calls))
        self.assertNotIn("test-secret", " ".join(logs.output))

    def test_permanent_statuses_and_redirects_are_not_retried(self):
        for status in [302, 400, 401, 403, 404, 422]:
            with self.subTest(status=status):
                calls = []

                def handle(request):
                    calls.append(request)
                    return httpx.Response(status, text="private provider body",
                                          headers={"Location": "https://another.example"})

                with httpx.Client(transport=httpx.MockTransport(handle)) as client, \
                        patch.object(transport, "_get_client", return_value=client), \
                        patch.object(transport, "sleep") as sleep:
                    with self.assertRaises(HTTPError) as error:
                        transport.open_provider_response(self.request())
                self.assertEqual(error.exception.code, status)
                self.assertNotIn("private provider body", str(error.exception))
                self.assertEqual(len(calls), 1)
                sleep.assert_not_called()

    def test_retry_after_is_respected(self):
        statuses = iter([429, 200])

        def handle(request):
            return httpx.Response(next(statuses), json={"ok": True}, headers={"Retry-After": "2"})

        with httpx.Client(transport=httpx.MockTransport(handle)) as client, \
                patch.object(transport, "_get_client", return_value=client), \
                patch.object(transport, "sleep") as sleep:
            transport.open_provider_response(self.request())
            sleep.assert_called_once_with(2)

    def test_long_retry_after_returns_failure_without_retrying_early(self):
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(429, headers={"Retry-After": "60"}))) as client, \
                patch.object(transport, "_get_client", return_value=client), \
                patch.object(transport, "sleep") as sleep:
            with self.assertRaises(HTTPError):
                transport.open_provider_response(self.request())
            sleep.assert_not_called()

    def test_server_failure_retries_are_bounded(self):
        calls = []

        def handle(request):
            calls.append(request)
            return httpx.Response(503)

        with httpx.Client(transport=httpx.MockTransport(handle)) as client, \
                patch.object(transport, "_get_client", return_value=client), \
                patch.object(transport, "sleep"):
            with self.assertRaises(HTTPError) as error:
                transport.open_provider_response(self.request())
        self.assertEqual(error.exception.code, 503)
        self.assertEqual(len(calls), 3)

    def test_gemini_retry_info_prevents_an_early_retry(self):
        body={"error":{"details":[{"@type":"type.googleapis.com/google.rpc.RetryInfo","retryDelay":"60s"}]}}
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(429,json=body))) as client, \
                patch.object(transport, "_get_client", return_value=client), \
                patch.object(transport, "sleep") as sleep:
            with self.assertRaises(HTTPError):
                transport.open_provider_response(self.request())
            sleep.assert_not_called()

    def test_certificate_failure_is_not_retried(self):
        def handle(request):
            raise httpx.ConnectError("CERTIFICATE_VERIFY_FAILED")

        with httpx.Client(transport=httpx.MockTransport(handle)) as client, \
                patch.object(transport, "_get_client", return_value=client), \
                patch.object(transport, "sleep") as sleep:
            with self.assertRaisesRegex(URLError, "certificate verification failed"):
                transport.open_provider_response(self.request())
            sleep.assert_not_called()

    def test_retry_cannot_exceed_remaining_budget(self):
        def handle(request):
            raise httpx.ConnectTimeout("unavailable")

        with httpx.Client(transport=httpx.MockTransport(handle)) as client, \
                patch.object(transport, "_get_client", return_value=client), \
                patch.object(transport, "monotonic", return_value=0), \
                patch.object(transport, "sleep") as sleep, transport.provider_budget(0.4):
            with self.assertRaises(URLError):
                transport.open_provider_response(self.request())
            sleep.assert_not_called()

    def test_retrieval_and_generation_share_one_deadline(self):
        clock = [0]

        def handle(request):
            clock[0] += 4
            return httpx.Response(200, json={"ok": True})

        with httpx.Client(transport=httpx.MockTransport(handle)) as client, \
                patch.object(transport, "_get_client", return_value=client), \
                patch.object(transport, "monotonic", side_effect=lambda: clock[0]), \
                transport.provider_budget(5):
            transport.open_provider_response(self.request())
            with self.assertRaises(TimeoutError):
                transport.open_provider_response(self.request())

    def test_response_size_is_bounded(self):
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"oversized"))) as client, \
                patch.object(transport, "_get_client", return_value=client), \
                patch.object(transport, "MAX_RESPONSE_BYTES", 4):
            with self.assertRaisesRegex(ValueError, "size limit"):
                transport.open_provider_response(self.request())


if __name__ == "__main__":
    unittest.main()
