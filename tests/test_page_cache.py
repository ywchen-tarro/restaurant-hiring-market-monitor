from unittest.mock import Mock, patch
from scraper.platforms.us168 import Scraper


def test_successful_page_is_reused_without_network(tmp_path):
    s = Scraper()
    response = Mock(text='valid html')
    with patch('scraper.platforms.base.config.LOG_DIR', tmp_path), patch.object(
        s, 'parse_page', return_value=[object()]
    ), patch('scraper.http_client.polite_get', return_value=response) as fetch:
        assert s.fetch_page(1) == 'valid html'
        assert s.fetch_page(1) == 'valid html'
        assert fetch.call_count == 1
        s.fetch_page(2)
        assert fetch.call_count == 2


def test_failed_or_unparseable_response_is_not_cached(tmp_path):
    s = Scraper()
    with patch('scraper.platforms.base.config.LOG_DIR', tmp_path), patch.object(
        s, 'parse_page', return_value=[]
    ), patch('scraper.http_client.polite_get', side_effect=[None, Mock(text='challenge'), None]) as fetch:
        assert s.fetch_page(1) is None
        assert s.fetch_page(1) == 'challenge'
        assert s.fetch_page(1) is None
        assert fetch.call_count == 3
