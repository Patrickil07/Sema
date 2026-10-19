from sema.normalize import normalize
from sema.office import table_to_speech, tsv_to_speech


def test_table_with_headers_and_row_labels():
    rows = [["Region", "Q1", "Q2"], ["North", "$1,200", "$1,350"], ["South", "$980", ""]]
    assert table_to_speech(rows) == "North. Q1: $1,200, Q2: $1,350.\nSouth. Q1: $980."


def test_headers_without_label_column():
    rows = [["Units", "Growth"], ["12", "4.5%"], ["15", "6%"]]
    assert table_to_speech(rows) == "Units: 12, Growth: 4.5%.\nUnits: 15, Growth: 6%."


def test_plain_grid_and_single_values():
    assert table_to_speech([["a", "b"], ["c", "d"]]) == "Row 1: a, b.\nRow 2: c, d."
    assert table_to_speech([["Total"], ["42"]]) == "Total. 42."
    assert table_to_speech([["", "Hello", ""]]) == "Hello"


def test_clipboard_tsv_reads_naturally():
    spoken = normalize(tsv_to_speech("Region\tQ1\r\nNorth\t$1,200\r\n"), force_english=True)
    assert spoken == "North. Q one: one thousand two hundred dollars."
