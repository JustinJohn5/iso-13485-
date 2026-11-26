"""真实 MySQL 8.4 测试副本验证访客身份、每日聚合和撤销。"""
from datetime import datetime, timedelta
from pathlib import Path
import secrets

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


@pytest.fixture
def visitor_db():
    config = dotenv_values(Path(__file__).resolve().parents[2] / '.env.test')
    url = config.get('DATABASE_URL')
    if not url:
        pytest.skip('请配置根目录 .env.test 的 MySQL 8.4 测试副本')
    assert config.get('APP_ENV') == 'test'
    assert (make_url(url).database or '').endswith('_codextest')
    from App.Models.Visitor import Visitor, VisitorDaily
    from App.Models.User import User

    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.execute(text('SELECT VERSION()')).scalar_one().startswith('8.4.')
        connection.commit()
    Visitor.__table__.create(engine, checkfirst=True)
    VisitorDaily.__table__.create(engine, checkfirst=True)
    with engine.connect() as connection:
        transaction = connection.begin()
        db = Session(bind=connection, join_transaction_mode='create_savepoint', expire_on_commit=False)
        user = User(email=f'visit-{secrets.token_hex(12)}@example.com', display_name='访客测试',
                    password_hash='synthetic-not-a-login', role='viewer', token_version=1, is_active=True)
        db.add(user)
        db.flush()
        yield db, user
        db.close()
        transaction.rollback()
    engine.dispose()


def test_cookie_digest_randomness_and_page_validation():
    from App.Services.VisitorTracking import cookie_digest, issue_visitor_cookie, validate_page
    from App.Utils.Errors import ApiError

    first, second = issue_visitor_cookie(), issue_visitor_cookie()
    assert first != second and len(first) >= 40
    assert len(cookie_digest(first)) == 64 and first not in cookie_digest(first)
    assert validate_page('/admin/') == '/admin/'
    for page in ('/?token=secret', '/unknown', '/' + 'a' * 200, 'https://evil.test/'):
        with pytest.raises(ApiError):
            validate_page(page)


def test_same_cookie_login_logout_counts_one_visitor_and_two_views(visitor_db):
    from App.Models.Visitor import Visitor
    from App.Services.VisitorTracking import VisitorIdentity, issue_visitor_cookie, overview, track_visit, visitors

    db, user = visitor_db
    current = datetime(2090, 11, 26, 12)
    cookie = issue_visitor_cookie()
    identity = VisitorIdentity(user.id, user.token_version, current + timedelta(hours=1))
    before = overview(db, at=current)
    track_visit(db, cookie, page='/', event='pageview', at=current)
    track_visit(db, cookie, page='/admin/', event='pageview', identity=identity, at=current)
    track_visit(db, cookie, page='/admin/', event='heartbeat', identity=identity, at=current)
    result = overview(db, at=current)
    assert result['today_views'] == before['today_views'] + 2
    assert result['today_visitors'] == before['today_visitors'] + 1
    assert result['online_users'] == before['online_users'] + 1
    row = db.execute(select(Visitor).where(Visitor.user_id == user.id)).scalar_one()
    assert row.cookie_hash != cookie
    uid = row.visitor_uid
    track_visit(db, cookie, page='/', event='logout', identity=identity, at=current)
    item = next(item for item in visitors(db, page=1, page_size=100, at=current)['items']
                if item['visitor_uid'] == uid)
    assert item['identity'] == 'anonymous' and item['user_id'] is None
    assert cookie not in str(item)


def test_midnight_heartbeat_and_online_expiry_do_not_add_pageviews(visitor_db):
    from App.Services.VisitorTracking import issue_visitor_cookie, overview, track_visit

    db, _ = visitor_db
    first = datetime(2090, 11, 26, 23, 59)
    tomorrow = first + timedelta(minutes=2)
    cookie = issue_visitor_cookie()
    before = overview(db, at=tomorrow)
    track_visit(db, cookie, page='/', event='pageview', at=first)
    track_visit(db, cookie, page='/', event='heartbeat', at=tomorrow)
    result = overview(db, at=tomorrow)
    assert result['today_visitors'] == before['today_visitors']
    assert result['today_views'] == before['today_views']
    track_visit(db, cookie, page='/', event='pageview', at=tomorrow)
    next_day = overview(db, at=tomorrow)
    assert next_day['today_visitors'] == before['today_visitors'] + 1
    assert next_day['today_views'] == before['today_views'] + 1
    assert overview(db, at=tomorrow + timedelta(minutes=6))['online_visitors'] == before['online_visitors']


@pytest.mark.parametrize('invalid', ['expired', 'revoked', 'inactive'])
def test_admin_never_treats_stale_identity_as_authenticated(visitor_db, invalid):
    from App.Services.VisitorTracking import VisitorIdentity, issue_visitor_cookie, overview, track_visit, visitors

    db, user = visitor_db
    current = datetime(2090, 11, 26, 12)
    before = overview(db, at=current)
    identity = VisitorIdentity(user.id, 1, current + timedelta(seconds=1))
    track_visit(db, issue_visitor_cookie(), page='/', event='pageview', identity=identity, at=current)
    if invalid == 'revoked':
        user.token_version = 2
    elif invalid == 'inactive':
        user.is_active = False
    db.flush()
    result = overview(db, at=current + timedelta(seconds=2))
    assert result['online_users'] == before['online_users']
    assert all(item['user_id'] != user.id for item in visitors(db, page=1, page_size=100,
                                                           at=current + timedelta(seconds=2))['items'])


def test_retention_cleanup_deletes_old_rows_in_bounded_batches(visitor_db):
    from App.Models.Visitor import Visitor, VisitorDaily
    from App.Services.VisitorTracking import cleanup_old_data

    db, _ = visitor_db
    current = datetime(2090, 11, 26, 12)
    track_cookie = 'a' * 43
    from App.Services.VisitorTracking import track_visit
    track_visit(db, track_cookie, page='/', event='pageview', at=current - timedelta(days=500))
    before_id = db.execute(select(Visitor.id).where(Visitor.cookie_hash != '')).scalar_one()
    result = cleanup_old_data(db, at=current, visitor_limit=1, daily_limit=1)
    assert result == {'visitors': 1, 'daily': 1}
    assert db.get(Visitor, before_id) is None
    assert db.execute(select(VisitorDaily.id)).first() is None
