from __future__ import annotations

import datetime

# anki interfaces
from aqt import mw
from aqt import gui_hooks
from aqt.qt import QMessageBox
from anki.lang import _
from anki.utils import ids2str
from aqt.utils import tooltip
from typing import List
import time

from aqt.utils import getFile, getSaveFile
from ast import literal_eval

# add on utilities
from . import ease_calculator

def announce(announcement):
    msg = QMessageBox(mw)
    msg.setStandardButtons(QMessageBox.Ok)
    msg.setText(_(announcement))
    msg.exec_()


def create_comparelog(local_rids: List[int]) -> None:
    local_rids.clear()
    local_rids.extend([id for id in mw.col.db.list("SELECT id FROM revlog")])

def review_cid_remote(local_rids: List[int]):
    local_rid_string = ids2str(local_rids)
    reviewed_cids = [
        cid
        for cid in mw.col.db.list(
            f"""SELECT DISTINCT cid
            FROM revlog
            WHERE id NOT IN {local_rid_string}
            WHERE type < 4
            """
        )  # type: 0=Learning, 1=Review, 2=relearn, 3=Relearning, 4=Manual
    ]
    return reviewed_cids


def adjust_ease_factors_background(card_ids: List[int]):
    from autoEaseFactor import suggested_factor
    
    # undo_entry = mw.col.add_custom_undo_entry("Adjust ease")
    mw.taskman.run_on_main(
        lambda: mw.progress.start(label="Adjusting ease", immediate=False)
    )

    cnt = 0
    cancelled = False

    for card_id in card_ids:
        if cancelled:
            break
        card = mw.col.getCard(card_id)
        print("old factor", card.factor)
        card.factor = suggested_factor(card=card, is_deck_adjustment=True)
        print("new factor", card.factor)
        mw.col.update_card(card)
        # mw.col.merge_undo_entries(undo_entry)
        cnt += 1
        if cnt % 500 == 0:
            mw.taskman.run_on_main(
                lambda: mw.progress.update(value=cnt, label=f"{cnt} cards adjusted")
            )
            if mw.progress.want_cancel():
                cancelled = True

    return f"Adjusted ease for {cnt} cards"

def adjust_ease(card_ids: List[int]):
    start_time = time.time()

    def on_done(future):
        mw.progress.finish()
        tooltip(f"{future.result()} in {time.time() - start_time:.2f} seconds")
        mw.col.reset()
        mw.reset()

    fut = mw.taskman.run_in_background(
        lambda: adjust_ease_factors_background(card_ids),
        on_done,
    )

    return fut

def auto_adjust_ease(local_rids: List[int], texts: List[str]):
    print("Local log length", len(local_rids))
    if len(local_rids) == 0:
        return

    remote_reviewed_cids = review_cid_remote(local_rids)

    print("remote_reviewed_cids",remote_reviewed_cids)

    fut = adjust_ease(
        card_ids=remote_reviewed_cids,
    )

    if fut:
        # wait for adjustment to finish
        texts.append(fut.result())

def export_ease_factors(deck_id):
    '''Saves a deck's ease factors using file picker.

    For some deck `deck_id`, prompts to save a file containing a
    dictionary that links card id keys to ease factors.
    '''
    deck_name = mw.col.decks.name_if_exists(deck_id)
    if deck_name is None:
        return

    # open file picker to store factors
    dt_now_str = str(datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    suggested_filename = "ease_factors_" + str(deck_id) + dt_now_str
    export_file = getSaveFile(mw, _("Export"), "export",
                              key="",
                              ext="",
                              fname=suggested_filename)
    if not export_file:
        return

    factors = {}
    card_ids = mw.col.find_cards(f'deck:"{deck_name}"')
    for card_id in card_ids:
        card = mw.col.getCard(card_id)
        factors[card_id] = card.factor
    with open(export_file, 'w') as export_file_object:
        export_file_object.write(str(factors))
    announce("Export complete!")


def import_ease_factors(deck_id, factors=None):
    '''Resets ease factors in a deck to a saved state.

    For deck `deck_id` and `factors`--a dictionary linking card id keys
    to ease factors--set the ease factors of the cards in the deck to the
    ease factors provided in `factors`.

    If factors is not provided, prompt user to load a file of ease values,
    such as one saved by `export_ease_factors()`.
    '''
    deck_name = mw.col.decks.name_if_exists(deck_id)
    if deck_name is None:
        print("Deck name not found on import_ease_factors, exiting...")
        return

    if factors is None:
        # open file picker to load factors
        import_file = getFile(mw, _("Import"), None,
                              filter="*", key="import")
        if import_file == []:
            # no file selected
            return
        with open(import_file, 'r') as import_file_object:
            factors = literal_eval(import_file_object.read())

    card_ids = mw.col.find_cards(f'deck:"{deck_name}"')
    for card_id in card_ids:
        card = mw.col.getCard(card_id)
        card.factor = factors.get(card_id, card.factor)
        card.flush()
    announce("Import complete!")


def add_deck_options(menu, deck_id):
    export_action = menu.addAction("Export Ease Factors (AEF)")
    export_action.triggered.connect(lambda _,
                                    did=deck_id: export_ease_factors(did))
    import_action = menu.addAction("Import Ease Factors (AEF)")
    import_action.triggered.connect(lambda _,
                                    did=deck_id: import_ease_factors(did))
    # adjust_action = menu.addAction("Adjust Ease Factors To Performance - Whole deck")
    # adjust_action.triggered.connect(lambda _,
                                    # did=deck_id: auto_adjust_ease(did))
    # adjust_action = menu.addAction("Adjust Ease Factors To Performance - Only studied today")
    # adjust_action.triggered.connect(lambda _,
    #                                 did=deck_id: adjust_ease_factors(did, True))
    

def init_deck_options():
    gui_hooks.deck_browser_will_show_options_menu.append(add_deck_options)

def init_sync_hook():
    local_rids = []
    texts = []
    gui_hooks.sync_will_start.append(lambda: create_comparelog(local_rids))
    gui_hooks.sync_did_finish.append(lambda: auto_adjust_ease(local_rids, texts))

init_deck_options()
init_sync_hook()
