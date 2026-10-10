from datetime import date, timedelta

PRIORITIES = {'beach': 'Beach', 'luxury': 'Luxury', 'family': 'Kids facilities',
              'all-inclusive': 'All inclusive', 'activities': 'Activities', 'spa': 'Spa',
              'golf': 'Golf', 'romance': 'Romance', 'value': 'Value'}
TRAVELLERS = {'couple': ('Couple', 'heart'), 'family': ('Family', 'users'),
              'honeymoon': ('Honeymoon', 'gem'), 'friends': ('Friends', 'handshake'), 'solo': ('Solo', 'user')}
DEPARTURES = ('Johannesburg', 'Cape Town', 'Durban', 'Other')
TAG_OPTIONS = tuple(PRIORITIES) + ('adults-only',)


def validate_brief(form):
    traveller = form.get('traveller', '')
    priorities = list(dict.fromkeys(form.getlist('priorities')))
    if traveller not in TRAVELLERS or not 1 <= len(priorities) <= 3 or any(p not in PRIORITIES for p in priorities):
        raise ValueError('Choose who is travelling and one to three priorities.')
    try:
        adults, children, infants = (int(form.get(key, '0')) for key in ('adults', 'children', 'infants'))
        nights = int(form.get('nights', '7'))
        budget = int(form['budget']) if form.get('budget', '').strip() else None
    except (ValueError, TypeError, KeyError):
        raise ValueError('Use whole numbers for travellers, nights and your budget.')
    if not (1 <= adults <= 6 and 0 <= children <= 4 and 0 <= infants <= 2 and 1 <= nights <= 30):
        raise ValueError('Choose 1-6 adults, 0-4 children, 0-2 infants and 1-30 nights. Ask Dirk about larger groups.')
    if (children or infants) and traveller != 'family':
        raise ValueError('Choose Family when children or infants are travelling.')
    if traveller == 'solo' and adults != 1:
        raise ValueError('Choose one adult for solo travel.')
    if budget is not None and not 1 <= budget <= 10000000:
        raise ValueError('Enter a positive budget in rand, or leave it blank.')
    basis, departure = form.get('budget_basis', ''), form.get('departure', '')
    if basis not in ('Total party', 'Per adult') or departure not in DEPARTURES:
        raise ValueError('Choose a budget basis and departure city.')
    travel_date = form.get('travel_date', '').strip()
    if travel_date:
        try:
            if date.fromisoformat(travel_date) < date.today():
                raise ValueError()
        except ValueError:
            raise ValueError('Choose a future travel date, or leave the date open.')
    return dict(traveller=traveller, priorities=priorities, adults=adults, children=children, infants=infants,
                nights=nights, budget=budget, budget_basis=basis, departure=departure,
                travel_date=travel_date, flexible=form.get('flexible') == 'on')


def reviewed_tags(resort):
    try:
        reviewed = date.fromisoformat(resort.planning_reviewed)
        if not resort.planning_source or not 0 <= (date.today() - reviewed).days <= 180:
            return set()
    except (ValueError, TypeError):
        return set()
    return set((resort.planning_tags or '').split(',')) & set(TAG_OPTIONS)


def shortlist(resorts, brief):
    ranked = []
    for resort in resorts:
        tags = reviewed_tags(resort)
        if not resort.published or not tags:
            continue
        family = brief['traveller'] == 'family'
        if family and ('family' not in tags or 'adults-only' in tags):
            continue
        if brief['travel_date'] and resort.unavailable_from and resort.unavailable_to:
            start = date.fromisoformat(brief['travel_date'])
            end = start + timedelta(days=brief['nights'])
            if start <= date.fromisoformat(resort.unavailable_to) and end > date.fromisoformat(resort.unavailable_from):
                continue
        matched = [p for p in brief['priorities'] if p in tags]
        # Value needs comparable live pricing, not an editorial tag or teaser price.
        matched = [p for p in matched if p != 'value']
        if not matched and not family:
            continue
        reasons = [PRIORITIES[p] for p in matched]
        if family and 'family' not in matched:
            reasons.append('Kids facilities')
        ranked.append(dict(resort=resort, reasons=reasons, score=len(matched)))
    return sorted(ranked, key=lambda item: (-item['score'], item['resort'].id))[:3]


def brief_text(brief, resorts):
    lines = ['Holiday planning brief', 'Traveller: ' + TRAVELLERS[brief['traveller']][0],
             f"Party: {brief['adults']} adults, {brief['children']} children, {brief['infants']} infants",
             'Priorities: ' + ', '.join(PRIORITIES[p] for p in brief['priorities']),
             f"Budget preference: R {brief['budget']:,} ({brief['budget_basis']})" if brief['budget'] else 'Budget: to discuss',
             'Travel date: ' + (brief['travel_date'] or 'Open'), f"Nights: {brief['nights']}",
             'Flexible dates: ' + ('Yes' if brief['flexible'] else 'No'), 'Departure: ' + brief['departure'],
             'Resorts to discuss: ' + (', '.join(r.name for r in resorts) or 'Advisor recommendation requested'),
             'Suitability only; price, room capacity and availability require confirmation.']
    return '\n'.join(lines)
