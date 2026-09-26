import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import x_native
import x_research


class TestTwittOffline(unittest.TestCase):
    def setUp(self):
        self.dummy_headers = {
            "authorization": "Bearer dummy",
            "cookie": "auth_token=dummy; ct0=dummy",
            "x-csrf-token": "dummy"
        }

    @patch("x_native.load_cookies")
    def test_build_headers(self, mock_cookies):
        mock_cookies.return_value = {"auth_token": "token123", "ct0": "csrf123"}
        headers = x_native.build_headers(mock_cookies.return_value)
        self.assertIn("authorization", headers)
        self.assertEqual(headers["x-csrf-token"], "csrf123")
        self.assertIn("auth_token=token123", headers["cookie"])

    @patch("x_native.gql_post")
    def test_like_success(self, mock_post):
        mock_post.return_value = (200, {"data": {"favorite_tweet": "Done"}})
        ok, detail = x_native.like("12345", headers=self.dummy_headers)
        self.assertTrue(ok)
        self.assertEqual(detail, {"favorite_tweet": "Done"})

    @patch("x_native.gql_post")
    def test_repost_success(self, mock_post):
        mock_post.return_value = (200, {"data": {"create_retweet": {"retweet_results": {"result": {"rest_id": "rt_999"}}}}})
        ok, detail = x_native.repost("12345", headers=self.dummy_headers)
        self.assertTrue(ok)
        self.assertEqual(detail.get("rest_id"), "rt_999")

    @patch("x_native.gql_post")
    def test_reply_success(self, mock_post):
        mock_post.return_value = (200, {"data": {"create_tweet": {"tweet_results": {"result": {"rest_id": "reply_123"}}}}})
        ok, detail = x_native.reply("12345", "test reply", headers=self.dummy_headers)
        self.assertTrue(ok)
        self.assertEqual(detail.get("rest_id"), "reply_123")

    @patch("x_native.gql_get")
    def test_user_lookup(self, mock_get):
        mock_get.return_value = (200, {"data": {"user": {"result": {"rest_id": "12", "core": {"screen_name": "jack", "name": "jack"}}}}})
        user, err = x_native.user_by_screen_name("jack", headers=self.dummy_headers)
        self.assertIsNone(err)
        self.assertEqual(user.get("rest_id"), "12")

    @patch("x_native._do")
    def test_follow(self, mock_do):
        mock_do.return_value = (200, {"id": 12, "screen_name": "jack", "following": True})
        ok, detail = x_native.follow("jack", headers=self.dummy_headers)
        self.assertTrue(ok)
        self.assertEqual(detail.get("screen_name"), "jack")

    @patch("x_native.read_tweet_text")
    def test_research_bridge(self, mock_read):
        mock_read.return_value = "@jack: test tweet"
        txt = x_research.read_tweet("20")
        self.assertEqual(txt, "@jack: test tweet")


if __name__ == "__main__":
    unittest.main()
