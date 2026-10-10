from types import SimpleNamespace

import pytest

from website.resort_media import featured_photo, media_for, validate_media


def entry(**changes):
    row = dict(name='Junior Suite', src='/static/resorts/tab/floor-plan-Im0.jpg',
               category='plan', room='Junior Suite', source='https://www.beachcomber.co.za/', note='2025-26')
    return dict(row, **changes)


@pytest.mark.parametrize('path', ['/static/resorts/../secret.jpg', 'https://other.test/photo.jpg',
                                 '/static/uploads/a%2fb.jpg', '/static/uploads/a.svg'])
def test_reject_unsafe_media_paths(path):
    with pytest.raises(ValueError):
        validate_media([entry(src=path)])


def test_reject_unsafe_source():
    with pytest.raises(ValueError):
        validate_media([entry(source='javascript:alert(1)')])


def test_missing_images_filtered_and_empty_override_respected():
    resort = SimpleNamespace(code='TAB')
    assert media_for(resort, {'media': [entry(src='/static/resorts/tab/missing.jpg')]}) == []
    assert media_for(resort, {'media': []}) == []


@pytest.mark.parametrize('code', ['VIC', 'MAU', 'CAN', 'TAB', 'SHA', 'DIN', 'PAR', 'RP'])
def test_every_resort_has_approved_photographs_and_map(code):
    rows = media_for(SimpleNamespace(code=code), {})
    assert sum(row['category'] == 'room' for row in rows) >= 4
    assert sum(row['category'] == 'resort' for row in rows) >= 2
    assert any(row['category'] == 'map' for row in rows)


def test_trou_aux_biches_has_seven_original_upright_plans():
    rows = media_for(SimpleNamespace(code='TAB'), {})
    plans = [row for row in rows if row['category'] == 'plan']
    assert len(plans) == 7
    assert len({row['room'] for row in plans}) == 7
    assert all(row.get('rotation', 0) == 0 for row in plans)
    assert all('2025-26' in row['note'] for row in plans)


@pytest.mark.parametrize('code', ['VIC', 'MAU', 'CAN', 'TAB', 'SHA', 'DIN', 'PAR', 'RP'])
def test_featured_photo_is_approved_resort_image(code):
    resort = SimpleNamespace(code=code)
    photo = featured_photo(resort, {})
    assert photo in media_for(resort, {})
    assert photo['category'] == 'resort'
    assert photo['src'].startswith('/static/resorts/')


def test_featured_photo_respects_editor_removal():
    assert featured_photo(SimpleNamespace(code='TAB'), {'media': []}) is None
