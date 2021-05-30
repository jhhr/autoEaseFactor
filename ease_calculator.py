import math


def moving_average(value_list, weight, init=None):
    """Provide (float) weighted moving average for list of values."""
    assert len(value_list) > 0
    if init is None:
        mavg = sum(value_list)/len(value_list)
    else:
        mavg = init
    for this_item in value_list:
        mavg = (mavg * (1 - weight))
        mavg += this_item * weight
    return mavg


def calculate_ease(config_settings, card_settings, leashed=True):
    """Return next ease factor based on config and card performance."""
    leash = config_settings['leash']
    target = config_settings['target']
    max_ease = config_settings['max_ease']
    min_ease = config_settings['min_ease']
    weight = config_settings['weight']
    starting_ease_factor = config_settings['starting_ease_factor']

    review_list = card_settings['review_list']
    factor_list = card_settings['factor_list']

    if factor_list is not None and len(factor_list) > 0:
        current_ease_factor = factor_list[-1]
    else:
        current_ease_factor = starting_ease_factor
    # if no reviews, just assume we're on target
    if review_list is None or len(review_list) < 1:
        success_rate = target
    else:
        success_list = [int(_ > 1) for _ in review_list]
        success_rate = moving_average(success_list, weight, init=target)

    # Ebbinghaus formula
    if success_rate > 0.99:
        success_rate = 0.99  # ln(1) = 0; avoid divide by zero error
    if success_rate < 0.01:
        success_rate = 0.01
    delta_ratio = math.log(target) / math.log(success_rate)
    if factor_list and len(factor_list) > 0:
        average_ease = moving_average(factor_list, weight)
    else:
        average_ease = starting_ease_factor
    suggested_factor = average_ease * delta_ratio
    if leashed:
        review_number_multiplier = 1 + (len(review_list) / 10)

        # allow smaller adjustments the closer we are to max_ease/min_ease
        if suggested_factor > starting_ease_factor:
            # make smaller adjustments above starting_ease_factor than below
            leash_multiplier = (((max_ease / current_ease_factor) ** (1/3))
                * ((suggested_factor / starting_ease_factor) ** (1/4))
                * (1 - current_ease_factor / max_ease)
                * (starting_ease_factor / current_ease_factor))

            ease_cap = min(
                max_ease, 
                (current_ease_factor + (
                    leash * leash_multiplier * review_number_multiplier)))
            if suggested_factor > ease_cap:
                suggested_factor = ease_cap

        if suggested_factor < starting_ease_factor:
            leash_multiplier = ((current_ease_factor / min_ease - 1)
                * ((starting_ease_factor / suggested_factor) ** (1/3))
                * (current_ease_factor / starting_ease_factor))

            ease_floor = max(
                min_ease,
                (current_ease_factor - (leash * leash_multiplier * review_number_multiplier))
                )
            if suggested_factor < ease_floor:
                suggested_factor = ease_floor
    return int(round(suggested_factor))


def calculate_all(config_settings, card_settings):
    """Recalculate all ease factors based on config and answers."""
    new_factor_list = [card_settings['factor_list'][0]]
    for count in range(1, 1 + len(card_settings['review_list'])):
        tmp_review_list = card_settings['review_list'][:count]
        tmp_card_settings = {'review_list': tmp_review_list,
                             'factor_list': new_factor_list}
        new_factor_list.append(calculate_ease(config_settings,
                                              tmp_card_settings))
    card_settings['factor_list'] = new_factor_list
    return card_settings
