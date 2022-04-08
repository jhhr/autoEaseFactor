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

def get_success_rate(review_list, weight, init):
    # Define hard answers as halfway between a failure and success
    rev_success_map = {
        0: 0,
        1: 0,
        2: 0.5,
        3: 1,
        4: 1.25,
    }
    success_list = [rev_success_map[_] for _ in review_list]
    return moving_average(success_list, weight, init)

# Offset the v3 scheduler factor changes, only use if using v3!
def get_factor_offset(answer):
    if answer is not None:
        return [200,150,0,-150][answer - 1]
    else:
        return 0

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
    valid_factor_list = [x for x in factor_list if x is not None] if factor_list else []
    current_ease_factor = None
    if len(valid_factor_list) > 0:
        current_ease_factor = valid_factor_list[-1]
    ## If value wasn't set or was set to zero for some reason, use starting ease
    if not current_ease_factor:
        current_ease_factor = starting_ease_factor

    # if no reviews, just assume we're on target
    if review_list is None or len(review_list) < 1:
        success_rate = target
        # factor_offset = 0
    else:
        success_rate = get_success_rate(review_list, weight, init=target)
        # factor_offset = get_factor_offset(review_list[-1])

    # Ebbinghaus formula
    if success_rate > 0.99:
        success_rate = 0.99  # ln(1) = 0; avoid divide by zero error
    if success_rate < 0.01:
        success_rate = 0.01
    delta_ratio = math.log(target) / math.log(success_rate)

    if len(valid_factor_list) > 0:
        average_ease = moving_average(valid_factor_list, weight)
    else:
        average_ease = starting_ease_factor
    suggested_factor = average_ease * delta_ratio

    if leashed:
    # factor will increase
        up_leash_multiplier =  (((max_ease / current_ease_factor) ** (1/3))
                # suggested_factor distance from starting ease increases multiplier slightly
                * ((suggested_factor / starting_ease_factor) ** (1/4))
                # Smaller multiplier the closer we are to max ease
                * (1 - current_ease_factor / max_ease)
                # Higher multiplier when below starting ease
                * (starting_ease_factor / current_ease_factor))
        #up_leash = min(leash, leash * up_leash_multiplier)

    # factor will decrease
        down_leash_multiplier = ((current_ease_factor / min_ease - 1)
                # suggested_factor distance from starting ease increases multiplier slightly
                * ((starting_ease_factor / suggested_factor) ** (1/3))
                # Smaller multiplier when below starting ease
                * (current_ease_factor / starting_ease_factor))

        ease_cap = min(
            max_ease, 
            (current_ease_factor + leash * up_leash_multiplier)
            )

        if suggested_factor > ease_cap:
            suggested_factor = ease_cap
            
        ease_floor = max(
                min_ease,
                (current_ease_factor - leash * down_leash_multiplier)
            )
        if suggested_factor < ease_floor:
            suggested_factor = ease_floor
        
    # return int(round(suggested_factor + factor_offset))
    return min(max(int(round(suggested_factor)), min_ease), max_ease)


def calculate_all(config_settings, card_settings):
    """Recalculate all ease factors based on config and answers."""
    new_factor_list = [config_settings['starting_ease_factor']]
    print(new_factor_list)
    for count in range(1, 1 + len(card_settings['review_list'])):
        tmp_review_list = card_settings['review_list'][:count]
        tmp_card_settings = {'review_list': tmp_review_list,
                             'factor_list': new_factor_list}
        new_factor_list.append(calculate_ease(config_settings,
                                              tmp_card_settings))
    card_settings['factor_list'] = new_factor_list
    return card_settings
