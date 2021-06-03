import math

# python imports are a mess
# standalone
if __name__ == "__main__":
    import ease_calculator
    calculate_ease = ease_calculator.calculate_ease
    calculate_all = ease_calculator.calculate_all
    try:
        import PySimpleGUIQt as PySGQt
    except ImportError:
        import _PySimpleGUIQt as PySGQt
else:
    # embedded
    from . import ease_calculator
    calculate_ease = ease_calculator.calculate_ease
    calculate_all = ease_calculator.calculate_all
    try:
        from . import PySimpleGUIQt as PySGQt
    except ImportError:
        from . import _PySimpleGUIQt as PySGQt



# TODO
# last factor missing from tooltip
# MAvg factor always 2500

def launch_simulator():
    layout = [[PySGQt.Text('Leash', size=(10, 1)),
               PySGQt.Input('300', key='leash')],
              [PySGQt.Text('Starting Ease', size=(10, 1)),
               PySGQt.Input('2500', key='starting_ease_factor')],
              [PySGQt.Text('Min Ease', size=(10, 1)),
               PySGQt.Input('10', key='min_ease')],
              [PySGQt.Text('Max Ease', size=(10, 1)),
               PySGQt.Input('7000', key='max_ease')],
              [PySGQt.Text('MAvg Weight', size=(10, 1)),
               PySGQt.Input('0.2', key='weight')],
              [PySGQt.Text('Target', size=(10, 1)),
               PySGQt.Input('0.85', key='target')],
              [PySGQt.Text('Answer History', size=(10, 1)),
               PySGQt.Input('1 3 3', key='answers')],
              [PySGQt.Text('Factor History', tooltip='Or initial ease factor '
                           'if recalculating ease history', size=(10, 1)),
                  PySGQt.Input('2500 1900 1700', tooltip='If recalculting'
                               ' history, starting ease factor will be taken'
                               ' from current deck starting ease', key='factors')],
              [PySGQt.Checkbox('Recalculate Ease History', default=True,
                               key='recalculate')],
              [PySGQt.Text('_'*40)],
              [PySGQt.Button('Calculate'),
               PySGQt.Text('', key='suggested_factor')],
              ]

    window = PySGQt.Window('Table Simulation', layout)

    def get_simulator_values():
        config_settings = {}
        config_settings['leash'] = int(values['leash'])
        config_settings['min_ease'] = int(values['min_ease'])
        config_settings['max_ease'] = int(values['max_ease'])
        config_settings['weight'] = float(values['weight'])
        config_settings['target'] = float(values['target'])
        config_settings['starting_ease_factor'] = int(values['starting_ease_factor'])
        card_settings = {}
        card_settings['review_list'] = [int(_) for _ in
                                        values['answers'].split()]
        card_settings['factor_list'] = [int(_) for _ in
                                        values['factors'].split()]
        return {"config_settings": config_settings,
                "card_settings": card_settings}

    def validate_simulator_inputs():
        valid = True
        field_labels = ['leash', 'starting_ease_factor', 'min_ease', 'max_ease',
                        'weight', 'target', 'answers', 'factors']

        # confirm all nonempty
        for field_label in field_labels:
            if values[field_label] in ['', None]:
                valid = False

        # confirm integer fields
        int_field_labels = ['leash', 'starting_ease_factor', 'min_ease', 'max_ease']
        for field_label in int_field_labels:
            for character in values[field_label].strip():
                if character not in '0123456789':
                    valid = False

        # confirm float fields
        float_field_labels = ['weight', 'target']
        for field_label in float_field_labels:
            for character in values[field_label].strip():
                if character not in '.0123456789':
                    valid = False
            if values[field_label].count('.') != 1:
                valid = False

        # confirm list fields
        list_field_labels = ['answers', 'factors']
        for field_label in list_field_labels:
            for character in values[field_label].strip():
                if character not in ' 0123456789':
                    valid = False
        return valid

    while True:
        event, values = window.read()
        if event is None or event in (PySGQt.WIN_CLOSED, 'Exit'):
            break
        elif event == 'Calculate':
            if validate_simulator_inputs():
                settings = get_simulator_values()
                config_settings = settings['config_settings']
                if values['recalculate']:
                    recalc_card_settings = {}
                    recalc_card_settings['review_list'] = [
                            int(_) for _ in values['answers'].split()]
                    recalc_card_settings['factor_list'] = [
                            int(values['factors'].split()[0])]
                    new_settings = calculate_all(config_settings,
                                                 recalc_card_settings)
                    new_factors = new_settings['factor_list']
                    window['suggested_factor'].update(new_factors)
                else:
                    window['suggested_factor'].update(
                            calculate_ease(**get_simulator_values()))
            else:
                window['suggested_factor'].update("Invalid entry")

    window.close()


if __name__ == '__main__':
    launch_simulator()
