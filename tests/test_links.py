import unittest
from unittest.mock import patch, MagicMock
import link_safety


class LinkTests(unittest.TestCase):
    def test_rejects_non_https_and_private_destinations(self):
        for url in ('file:///etc/passwd', 'http://example.org', 'https://user:pass@example.org', 'https://example.org:8080'):
            self.assertFalse(link_safety.reachable(url))
        for address in ('127.0.0.1', '10.1.1.1', '169.254.169.254', '::1'):
            with patch('socket.getaddrinfo', return_value=[(None, None, None, None, (address, 443))]):
                self.assertFalse(link_safety.reachable('https://example.org'))

    def test_redirect_is_revalidated_before_connecting(self):
        with patch.object(link_safety, 'public_target', side_effect=[('example.org', '93.184.216.34', '/'), ValueError('private')]), patch.object(link_safety, 'PublicHTTPSConnection') as cls:
            response = cls.return_value.getresponse.return_value
            response.status = 302
            response.getheader.return_value = 'https://127.0.0.1/private'
            self.assertFalse(link_safety.reachable('https://example.org'))
            self.assertEqual(cls.call_count, 1)

    def test_blocked_responses_are_not_verified(self):
        with patch.object(link_safety, 'public_target', return_value=('example.org', '93.184.216.34', '/')), patch.object(link_safety, 'PublicHTTPSConnection') as cls:
            for code in (401, 403, 429, 500):
                cls.return_value.getresponse.return_value.status = code
                self.assertFalse(link_safety.reachable('https://example.org'))
            cls.return_value.getresponse.return_value.status = 200
            self.assertTrue(link_safety.reachable('https://example.org'))

    def test_connection_uses_validated_ip_and_original_tls_hostname(self):
        connection = link_safety.PublicHTTPSConnection('example.org', '93.184.216.34', 2)
        connection._context = MagicMock()
        with patch('socket.create_connection') as connect:
            connection.connect()
            connect.assert_called_once_with(('93.184.216.34', 443), 2)
            self.assertEqual(connection._context.wrap_socket.call_args.kwargs['server_hostname'], 'example.org')
