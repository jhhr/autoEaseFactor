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
from .ease_calculator import calculate_ease, get_success_rate, moving_average


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

def get_all_reps_with_ids(card=mw.reviewer.card):
    return mw.col.db.all("select id, ease from revlog where cid = ? and "
                          "type IN (0, 1, 2, 3)", card.id)


def get_reviews_only(card=mw.reviewer.card):
    return mw.col.db.list(("select ease from revlog where type = 1"
                           " and cid = ?"), card.id)


def get_ease_factors(card=mw.reviewer.card):
    return mw.col.db.list("select factor from revlog where cid = ?"
                          " and factor > 0 and type IN (0, 1, 2, 3)",
                          card.id)


def get_starting_ease(card=mw.reviewer.card):
    deck_id = card.did
    if card.odid:
        deck_id = card.odid
    try:
        deck_starting_ease = mw.col.decks.config_dict_for_deck_id(
                deck_id)['new']['initialFactor']
    except KeyError:
        deck_starting_ease = 2500
    return deck_starting_ease


def get_rev_conf(card=mw.reviewer.card):
    deck_id = card.did
    if card.odid:
        deck_id = card.odid
    try:
        deck_easy_fct = mw.col.decks.config_dict_for_deck_id(
                deck_id)['rev']['ease4']
        print('deck_easy_fct', deck_easy_fct)
    except KeyError:
        deck_easy_fct = 1.3
    try:
        deck_hard_fct = mw.col.decks.config_dict_for_deck_id(
                deck_id)['rev']['hardFactor']
        print('deck_hard_fct', deck_hard_fct)
    except KeyError:
        deck_hard_fct = 1.2
    try:
        deck_max_ivl = mw.col.decks.config_dict_for_deck_id(
                deck_id)['rev']['maxIvl']
    except KeyError:
        deck_max_ivl = 3650        
    try:
        deck_again_fct = mw.col.decks.config_dict_for_deck_id(
                deck_id)['lapse']['mult']
        print('deck_again_fct',deck_again_fct)
    except KeyError:
        deck_max_ivl = 0
    return {
        'deck_easy_fct': deck_easy_fct,
        'deck_hard_fct': deck_hard_fct,
        'deck_max_ivl': deck_max_ivl,
        'deck_again_fct': deck_again_fct,
         
    }


def suggested_factor(card=mw.reviewer.card, new_answer=None, prev_card_factor=None, leashed=True, is_deck_adjustment=False):
    """Loads card history from anki and returns suggested factor"""

    deck_starting_ease = get_starting_ease(card)
    config_settings['starting_ease_factor'] = deck_starting_ease

    # Wraps calculate_ease()
    card_settings = {}
    card_settings['id'] = card.id
    card_settings['is_review_card'] = card.type == 2
    # If doing deck adjustment, rewrite all past factors in revlog
    if is_deck_adjustment:
        all_reps = get_all_reps_with_ids(card)
        card_settings['factor_list'] = [deck_starting_ease]
        for i in range(len(all_reps)):
            rep_id = all_reps[i][0]
            card_settings['review_list'] = [_[1] for _ in all_reps[0:i]]
            new_factor = calculate_ease(config_settings, card_settings,
                                          leashed)
            mw.col.db.execute("update revlog set factor = ? where id = ?", new_factor, rep_id)
            card_settings['factor_list'].append(new_factor)
    if reviews_only:
        card_settings['review_list'] = get_reviews_only(card)
    else:
        card_settings['review_list'] = get_all_reps(card)
    if new_answer is not None:
        append_answer = new_answer
        card_settings['review_list'].append(append_answer)
    factor_list = get_ease_factors(card)
    if factor_list is not None and len(factor_list) > 0:
        factor_list[-1] = prev_card_factor
    card_settings['factor_list'] = factor_list
    # Ignore latest ease if you are applying algorithm from deck settings
    if new_answer is None and len(card_settings['factor_list']) > 1:
        card_settings['factor_list'] = card_settings['factor_list'][:-1]


    return calculate_ease(config_settings, card_settings,
                                          leashed)


def get_stats(card=mw.reviewer.card, new_answer=None, prev_card_factor=None):
    rep_list = get_all_reps(card)
    if new_answer:
        rep_list.append(new_answer)
    factor_list = get_ease_factors(card)
    weight = config_settings['weight']
    target = config_settings['target']

    if rep_list is None or len(rep_list) < 1:
        success_rate = target
    else:
        success_rate = get_success_rate(rep_list,
                                                      weight, init=target)
    if factor_list and len(factor_list) > 0:
        average_ease = moving_average(factor_list, weight)
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
        last_rev_factor = factor_list[-1]
    else:
        last_rev_factor = None
    delta_ratio = math.log(target) / math.log(success_rate)
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
    msg += f"MAvg factor: {round(average_ease, 2)}<br>"
    msg += f""" (delta: {round(delta_ratio, 2)})<br>"""
    if last_rev_factor == prev_card_factor:
        msg += f"Last rev factor: {last_rev_factor}<br>"
    else:
        msg += f"Last rev factor: {last_rev_factor}"
        msg += f" (actual: {prev_card_factor})<br>"
        
    if card.queue != 2 and reviews_only:
        msg += f"New factor: NONREVIEW, NO CHANGE<br>"
    else:
        new_factor = suggested_factor(card, new_answer, prev_card_factor)
        unleashed_factor = suggested_factor(card, new_answer, prev_card_factor, leashed=False,)
        if new_factor == unleashed_factor:
            msg += f"New factor: {new_factor}<br>"
        else:
            msg += f"""New factor: {new_factor}"""
            msg += f""" (unleashed: {unleashed_factor})<br>"""
    msg += f"Rep list: {printable_rep_list}<br>"
    return msg


def display_stats(new_answer=None, prev_card_factor=None):
    card = mw.reviewer.card
    msg = get_stats(card, new_answer, prev_card_factor)
    tooltip_args = {
        'msg': msg,
        'period': stats_duration,
        'x_offset': 12,
        'y_offset': 240,
    }

    tooltip(**tooltip_args)


def adjust_factor(ease_tuple,
                  reviewer=reviewer.Reviewer,
                  card=mw.reviewer.card):
    assert card is not None
    new_answer = ease_tuple[1]
    prev_card_factor = card.factor
    if card.queue == 2 or not reviews_only:
        card.factor = suggested_factor(card, new_answer, prev_card_factor)
    if stats_enabled:
        display_stats(new_answer, prev_card_factor)
    return ease_tuple


gui_hooks.reviewer_will_answer_card.append(adjust_factor)
