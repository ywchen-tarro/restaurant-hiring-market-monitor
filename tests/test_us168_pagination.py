from datetime import date, timedelta
from unittest.mock import patch

from scraper.platforms.us168 import Scraper


def test_old_pinned_job_does_not_stop_before_recent_jobs():
    today = date.today()
    old = today - timedelta(days=30)
    recent = today - timedelta(days=2)
    def record(id, day, top):
        from datetime import datetime
        return {'id': id, 'title': '中餐招聘炒锅', 'top': top,
                'bizUpdateTime': int(datetime.combine(day, datetime.min.time()).timestamp()*1000)}
    pages = [[record('pinned', old, 2)], [record('recent', recent, 1)],
             [record('old', old, 3)]]
    scraper = Scraper()
    with patch.object(scraper, 'fetch_page', return_value='html'), patch(
        'scraper.platforms.us168._extract_records', side_effect=pages
    ):
        posts = scraper.run(days_back=7)
    assert [p.id for p in posts] == ['us168_recent']
    assert scraper.last_diagnostics['pages_fetched'] == 3
