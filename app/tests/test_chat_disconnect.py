"""HTTP cancellation sees peer EOF during silent prefill, without reading bytes."""
from contextlib import closing
import io
import json
import socket
import unittest
from unittest.mock import Mock, patch

import server
from app import bridge


class ChatDisconnectTests(unittest.TestCase):
    def test_open_idle_socket_does_not_cancel(self):
        local, peer = socket.socketpair()
        with closing(local), closing(peer):
            self.assertFalse(server._client_disconnected(local))

    def test_peer_close_and_half_close_cancel(self):
        local, peer = socket.socketpair()
        with closing(local), closing(peer):
            peer.shutdown(socket.SHUT_WR)
            self.assertTrue(server._client_disconnected(local))
        local, peer = socket.socketpair()
        with closing(local):
            peer.close()
            self.assertTrue(server._client_disconnected(local))

    def test_pending_data_is_preserved_and_not_mistaken_for_eof(self):
        local, peer = socket.socketpair()
        with closing(local), closing(peer):
            peer.sendall(b'next request')
            self.assertFalse(server._client_disconnected(local))
            self.assertFalse(server._client_disconnected(local))
            self.assertEqual(local.recv(12), b'next request')
            self.assertFalse(server._client_disconnected(local))
            peer.shutdown(socket.SHUT_WR)
            self.assertTrue(server._client_disconnected(local))

    def test_non_socket_bridge_transport_and_closed_local_socket(self):
        self.assertFalse(server._client_disconnected(None))
        self.assertFalse(server._client_disconnected(io.BytesIO()))
        local, peer = socket.socketpair()
        with closing(peer):
            local.close()
            self.assertTrue(server._client_disconnected(local))

    def test_native_bridge_exchange_cancel_is_visible_without_transport_reads(self):
        exchange = bridge.Exchange(Mock(), 'POST', '/api/chat', b'private body', None, False)
        connection = bridge._Sock(b'private body', exchange)
        with patch.object(connection, 'makefile', side_effect=AssertionError('must not read the transport')):
            self.assertFalse(server._client_disconnected(connection))
            exchange.cancel()
            self.assertTrue(server._client_disconnected(connection))
        self.assertTrue(exchange.stopped)

    def test_chat_callback_observes_native_cancel_before_any_sse_write(self):
        exchange = bridge.Exchange(Mock(), 'POST', '/api/chat', b'', None, False)
        handler = object.__new__(server.Handler)
        handler.connection = bridge._Sock(b'', exchange)
        handler.path = '/api/chat'
        request = json.dumps({'messages': [{'role': 'user', 'content': 'fixture'}]}).encode()
        handler.headers = {'Content-Length': str(len(request))}
        handler.rfile = io.BytesIO(request)
        handler.wfile = io.BytesIO()
        handler.host_ok = handler.origin_ok = handler.lan_ok = lambda: True
        handler.send_response = handler.send_header = handler.end_headers = lambda *args: None
        observed = []

        def chat(messages, about, emit, cancelled):
            observed.append(cancelled())
            exchange.cancel()  # the shell's existing Stop path, during silent prefill
            observed.append(cancelled())
            emit({'type': 'delta', 'text': 'must not be written'})

        with patch.object(server.assistant, 'model_status', return_value={'online': True}), \
                patch.object(server.assistant, 'chat', side_effect=chat):
            handler.handle_post()
        self.assertEqual(observed, [False, True])
        self.assertEqual(handler.wfile.getvalue(), b'')

    def test_chat_callback_observes_close_before_any_model_output(self):
        local, peer = socket.socketpair()
        with closing(local), closing(peer):
            handler = object.__new__(server.Handler)
            handler.connection = local
            handler.path = '/api/chat'
            request = json.dumps({'messages': [{'role': 'user', 'content': 'fixture'}]}).encode()
            handler.headers = {'Content-Length': str(len(request))}
            handler.rfile = io.BytesIO(request)
            handler.wfile = io.BytesIO()
            handler.host_ok = handler.origin_ok = handler.lan_ok = lambda: True
            handler.send_response = handler.send_header = handler.end_headers = lambda *args: None
            observed = []

            def chat(messages, about, emit, cancelled):
                self.assertEqual(handler.rfile.tell(), len(request))
                observed.append(cancelled())
                peer.shutdown(socket.SHUT_WR)
                # Silent native prompt evaluation has not emitted an SSE write.
                observed.append(cancelled())
                emit({'type': 'token', 'text': 'must not be written'})

            with patch.object(server.assistant, 'model_status', return_value={'online': True}), \
                    patch.object(server.assistant, 'chat', side_effect=chat):
                handler.handle_post()
            self.assertEqual(observed, [False, True])
            self.assertEqual(handler.wfile.getvalue(), b'')


if __name__ == '__main__':
    unittest.main()
