"""Original planning content and sourced supplier facts, never invented advisor opinions."""
from .models import Page, Resort, Setting, db

BASE = 'https://www.beachcomber.co.za/hotels/mauritius/'
FACTS = {
    'MAU': ('mauricia-beachcomber-resort-spa', 'beach,family,activities,spa,all-inclusive',
            'Compare a room near the beachfront with a family apartment; they are different accommodation choices.'),
    'VIC': ('victoria-beachcomber-resort-spa', 'beach,family,spa,activities,all-inclusive,romance',
            'The adults-only wing is separate from family accommodation. Confirm the exact wing and room type.'),
    'TAB': ('trou-aux-biches-beachcomber-golf-resort-spa', 'beach,family,spa,romance,luxury',
            'Private pools belong to selected suite and villa categories, not every room. Confirm the category in your quote.'),
    'DIN': ('dinarobin-beachcomber-golf-resort-spa', 'beach,family,golf,spa,luxury,romance',
            'Adults-only accommodation is in a separate crescent. Supplier notice: closed 15 May-16 October 2027; confirm reopening before travel.'),
    'PAR': ('paradis-beachcomber-golf-resort-spa', 'beach,family,golf,spa,activities',
            'Golf-related costs and room location need checking. Dinarobin facilities are unavailable during its announced 2027 closure.'),
    'SHA': ('shandrani-beachcomber-resort-spa', 'beach,family,all-inclusive,activities,spa,romance',
            'Compare the named all-inclusive packages: their inclusions differ. Adults-only rooms are in a separate wing.'),
    'CAN': ('canonnier-beachcomber-golf-resort-spa', 'beach,family,all-inclusive,spa,romance',
            'Garden-facing and sea-facing accommodation differ; confirm which view and room arrangement your quote includes.'),
    'RP': ('royal-palm-beachcomber-luxury', 'beach,luxury,spa,family',
           'Confirm the suite category and dining inclusions. Do not assume an all-inclusive package is available.'),
}
GUIDES = [
    ('choose-your-resort', 'How to choose your Mauritius resort', 'Start with your travel needs, not a star rating.', 'resort-1.jpg',
     '## Start with the holiday you want\n\nChoose three things that matter most: beach time, facilities for children, a particular meal plan, activities or a quieter setting. A longer wish list can hide your real priorities.\n\n## Compare the same details\n\nLook at location, actual room category, meal-plan inclusions and total party cost. A family apartment and a standard double room are not interchangeable. A resort with an adults-only wing is not necessarily an adults-only property.\n\n## Build a manageable shortlist\n\nChoose up to three resorts. Write down one reason to prefer each and one question you still need answered. Our finder covers Beachcomber resorts only; it suggests suitability, not confirmed availability.\n\n## Ask for a quote with context\n\nShare your departure city, preferred dates, nights, party size and budget basis. Exact passenger ages and room arrangements need confirming before a supplier quotation.'),
    ('meal-plans', 'Half board or all inclusive?', 'Compare what is included before comparing the headline price.', 'resort-3.jpg',
     '## Start with the named package\n\nAsk which meals, drinks and venues the quoted plan includes. Do not assume every resort uses identical rules or that all inclusive means every menu item and activity is free.\n\n## Think about your days\n\nIf you expect to spend most days at the resort, compare an inclusive option with the meals and drinks you would otherwise buy. If you plan to explore, consider whether you will use those inclusions.\n\n## Request a like-for-like comparison\n\nKeep dates, flights, room category and number of nights the same. Then compare the meal-plan supplement and exclusions. Check restaurant booking requirements, premium items, minibar rules and arrival/departure-day meals.\n\n## Keep an allowance for extras\n\nSpa treatments, excursions and some activities may be additional. Ask Dirk to explain the written inclusions in your specific quote; do not rely on a general package label.'),
    ('package-prices', 'How to compare Mauritius package prices', 'Understand sharing rates, flight assumptions and total costs.', 'resort-vic.jpg',
     '## A from-price is a starting point\n\nA displayed special may depend on dates, departure city, room type and occupancy. It is not confirmation that the same price is available for your party.\n\n## Compare one set of assumptions\n\nCheck nights, travel dates, return flights, taxes, baggage, transfers, room category and meal plan. Ask what is excluded and when the offer can be booked.\n\n## Per person is not your family total\n\nA per-person-sharing rate should not be multiplied blindly to cost a family. Child rates and room arrangements can change the calculation. Ask for a total-party quote and its breakdown.\n\n## Know what has been confirmed\n\nA supplier quote still needs its availability and terms checked. If no verified price is displayed, request a quote rather than assuming the holiday is free or unavailable. On this site, a suitability shortlist is not a price comparison.'),
    ('family-rooms', 'Planning a Mauritius family holiday', 'Room layout matters as much as resort facilities.', 'resort-vic.jpg',
     '## Begin with who is travelling\n\nShare the number of adults, children and infants. Exact ages at travel matter when the supplier prices the trip and confirms room eligibility. Avoid posting children\'s personal details in a public shortlist link.\n\n## Decide how you want to sleep\n\nCompare a shared room, a family apartment and connecting rooms. Ask whether the connection is confirmed, what beds are supplied and which age/occupancy rules apply.\n\n## Check facilities against your children\n\nAsk about club age ranges, opening times, supervision, swimming arrangements and any charges. A kids-club label alone does not answer those questions.\n\n## Separate a resort from its wings\n\nSome Beachcomber properties offer adults-only accommodation alongside family facilities. Your quote must specify a suitable room and wing. A finder result does not confirm that a room can accommodate your family.'),
    ('coast-and-location', 'Choosing your Mauritius location', 'Use location to make your shortlist more practical.', 'resort-2.jpg',
     '## Start with a map and your plans\n\nThink about whether you want days at the resort, access to a town, golf or excursions. Location is one decision factor, not a guarantee of weather or sea conditions.\n\n## Compare your actual resorts\n\nOur Beachcomber catalogue includes locations such as Grand Baie, Trou aux Biches, Pointe aux Piments, Le Morne and Blue Bay. Compare the specific properties rather than assuming every hotel on a coast feels the same.\n\n## Check time and convenience\n\nAsk about airport transfers, excursion pickup arrangements and the transport you will need. Avoid judging travel times solely by straight-line distance.\n\n## Balance setting with accommodation\n\nAn appealing coastline does not resolve room layout, meal plan or budget. Compare those details alongside location, and ask Dirk about seasonal considerations for your intended dates.'),
    ('honeymoon-planning', 'Planning your Mauritius honeymoon', 'Choose the atmosphere and details that suit both of you.', 'resort-3.jpg',
     '## Define your ideal days together\n\nDecide whether you want a quiet setting, activities, spa time, excursions or easy dining. Romance is personal: a resort label is not a substitute for those preferences.\n\n## Confirm the room, not just the property\n\nCheck location, view, privacy and any adults-only wing restrictions. Photos of a premium suite do not mean that suite is included in an entry-level quote.\n\n## Check offer eligibility\n\nAsk whether a honeymoon offer applies to your dates and accommodation, and which documents or wedding-date details the supplier requires. Do not assume promotions combine.\n\n## Make the enquiry specific\n\nInclude your departure city, dates, nights and budget basis. Mention the experience you want and any essentials; Dirk can then compare options with a personalised supplier quote.'),
]


def setup_hybrid():
    if db.session.get(Setting, 'hybrid_content_initialized'):
        return
    for resort in db.session.execute(db.select(Resort)).scalars():
        if resort.code in FACTS and not resort.planning_source and not resort.planning_tags:
            path, tags, caution = FACTS[resort.code]
            resort.planning_tags, resort.planning_source = tags, BASE + path
            resort.planning_reviewed, resort.consideration = '2026-10-03', caution
            if resort.code == 'DIN':
                resort.unavailable_from, resort.unavailable_to = '2027-05-15', '2027-10-16'
    for slug, title, summary, image, body in GUIDES:
        if not db.session.execute(db.select(Page).where(Page.slug == 'guide-' + slug)).scalar_one_or_none():
            db.session.add(Page(slug='guide-' + slug, title=title, body=body, published=True))
    db.session.add(Setting(key='hybrid_content_initialized', value='yes'))
    db.session.commit()
