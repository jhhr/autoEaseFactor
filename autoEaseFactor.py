# inspired by https://eshapard.github.io/

import math

# anki interfaces
from anki import version
from aqt import mw
from aqt import gui_hooks
from aqt import reviewer
from aqt.utils import tooltip
from aqt.qt import QMessageBox
from anki.lang import _


# add on utilities
from . import ease_calculator
from . import semver

if semver.Version(version) >= semver.Version("2.1.26"):
    from . import deck_settings
    # window vs. widget error
    # from . import menu_action

config = mw.addonManager.getConfig(__name__)

target_ratio = config.get('target_ratio', 0.85)
moving_average_weight = config.get('moving_average_weight', 0.2)
stats_enabled = config.get('stats_enabled', True)
stats_duration = config.get('stats_duration', 5000)

min_ease = config.get('min_ease', 1000)
max_ease = config.get('max_ease', 5000)
leash = config.get('leash', 100)
reviews_only = config.get('reviews_only', False)

config_settings = {
    'leash': leash,
    'min_ease': min_ease,
    'max_ease': max_ease,
    'weight': moving_average_weight,
    'target': target_ratio,
    'starting_ease_factor': None,
    'reviews_only': reviews_only
    }


def get_all_reps(card=mw.reviewer.card):
    return mw.col.db.list("select ease from revlog where cid = ? and "
                          "type IN (0, 1, 2, 3)", card.id)


def get_reviews_only(card=mw.reviewer.card):
    return mw.col.db.list(("select ease from revlog where type = 1"
                           " and cid = ?"), card.id)


def get_ease_factors(card=mw.reviewer.card):
    return mw.col.db.list("select factor from revlog where cid = ?"
                          " and factor > 0 and type IN (0, 1, 2, 3)",
                          card.id)

def get_current_factor(card=mw.reviewer.card):
    return mw.col.db.list("select factor from cards where id = ?", card.id)


def get_starting_ease(card=mw.reviewer.card):
    deck_id = card.did
    if card.odid:
        deck_id = card.odid
    try:
        deck_starting_ease = mw.col.decks.confForDid(
                deck_id)['new']['initialFactor']
    except KeyError:
        deck_starting_ease = 2500
    return deck_starting_ease


def suggested_factor(card=mw.reviewer.card, new_answer=None, leashed=True):
    """Loads card history from anki and returns suggested factor"""

    """Wraps calculate_ease()"""
    card_settings = {}
    card_settings['current_factor'] = get_current_factor(card)
    card_settings['is_review_card'] = card.type == 2
    if reviews_only:
        card_settings['review_list'] = get_reviews_only(card)
    else:
        card_settings['review_list'] = get_all_reps(card)
    if new_answer is not None:
        append_answer = new_answer
        # Use hard answers during review to make a one-time drop in factor
        if card.type == 2 and append_answer == 2:
            append_answer = 1
        card_settings['review_list'].append(append_answer)
    card_settings['factor_list'] = get_ease_factors(card)
    # Ignore latest ease if you are applying algorithm from deck settings
    if new_answer is None and len(card_settings['factor_list']) > 1:
        card_settings['factor_list'] = card_settings['factor_list'][:-1]

    deck_starting_ease = get_starting_ease(card)
    config_settings['starting_ease_factor'] = deck_starting_ease

    return ease_calculator.calculate_ease(config_settings, card_settings,
                                          leashed)


def get_stats(card=mw.reviewer.card, new_answer=None):
    rep_list = get_all_reps(card)
    if new_answer:
        rep_list.append(new_answer)
    factor_list = get_ease_factors(card)
    weight = config_settings['weight']
    target = config_settings['target']

    if rep_list is None or len(rep_list) < 1:
        success_rate = target
    else:
        success_list = [int(_ > 1) for _ in rep_list]
        success_rate = ease_calculator.moving_average(success_list,
                                                      weight, init=target)
    if factor_list and len(factor_list) > 0:
        average_ease = ease_calculator.moving_average(factor_list, weight)
    else:
        if config_settings['starting_ease_factor'] is None:
            config_settings['starting_ease_factor'] = get_starting_ease(card)
        average_ease = config_settings['starting_ease_factor']

    # add last review (maybe simplify by doing this after new factor applied)
    printable_rep_list = ""
    if len(rep_list) > 0:
        truncated_rep_list = rep_list[-10:]
        if len(rep_list) > 10:
            printable_rep_list += '..., '
        printable_rep_list += str(truncated_rep_list[0])
        for rep_result in truncated_rep_list[1:]:
            printable_rep_list += ", " + str(rep_result)
    if factor_list and len(factor_list) > 0:
        last_factor = factor_list[-1]
    else:
        last_factor = None
    card_types = {0: "new", 1: "learn", 2: "review", 3: "relearn"}
    queue_types = {0: "new",
                   1: "relearn",
                   2: "review",
                   3: "day (re)lrn",
                   4: "preview",
                   -1: "suspended",
                   -2: "sibling buried",
                   -3: "manually buried"}

    msg = f"card ID: {card.id}<br>"
    msg += (f"Card Queue (Type): {queue_types[card.queue]}"
            f" ({card_types[card.type]})<br>")
    msg += f"MAvg success rate: {round(success_rate, 4)}<br>"
    msg += f"Last factor: {last_factor}<br>"
    msg += f"MAvg factor: {round(average_ease, 2)}<br>"
    if card.queue != 2 and reviews_only:
        msg += f"New factor: NONREVIEW, NO CHANGE<br>"
    else:
        new_factor = suggested_factor(card, new_answer)
        unleashed_factor = suggested_factor(card, new_answer, leashed=False)
        if new_factor == unleashed_factor:
            msg += f"New factor: {new_factor}<br>"
        else:
            msg += f"""New factor: {new_factor}"""
            msg += f""" (unleashed: {unleashed_factor})<br>"""
    msg += f"Rep list: {printable_rep_list}<br>"
    return msg


def display_stats(new_answer=None):
    card = mw.reviewer.card
    msg = get_stats(card, new_answer)
    tooltip_args = {'msg': msg, 'period': stats_duration}
    if semver.Version(version) > semver.Version("2.1.30"):
        tooltip_args.update({'x_offset': 12, 'y_offset': 240})
    tooltip(**tooltip_args)


def adjust_factor(ease_tuple,
                  reviewer=reviewer.Reviewer,
                  card=mw.reviewer.card):
    assert card is not None
    new_answer = ease_tuple[1]
    if card.queue == 2 or not reviews_only:
        card.factor = suggested_factor(card, new_answer)
    if stats_enabled:
        display_stats(new_answer)
    return ease_tuple


gui_hooks.reviewer_will_answer_card.append(adjust_factor)
