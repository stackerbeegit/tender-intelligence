from app.intelligence.extraction.citations import normalise, quote_on_page

PAGE = (
    "Section 5: Pre-Qualification Criteria\n"
    "The bidder must have an average annual turnover of at least Rs. 10 Crore \n"
    "during the last three financial years.\n"
    "The bidder shall maintain “24x7” support – including holidays.\n"
    "Applicants with docu-\nmented experience are preferred."
)


def test_quote_spanning_pdf_line_break_matches():
    assert quote_on_page(
        "The bidder must have an average annual turnover of at least Rs. 10 Crore during the last three financial years.",
        PAGE,
    )


def test_curly_quotes_dashes_and_case_are_normalised():
    assert quote_on_page('the bidder shall maintain "24x7" support - including holidays.', PAGE)


def test_line_end_hyphenation_is_rejoined():
    assert quote_on_page("Applicants with documented experience are preferred.", PAGE)


def test_paraphrase_does_not_match():
    assert not quote_on_page("Average turnover must be at least Rs. 10 Crore over three years.", PAGE)


def test_invented_number_does_not_match():
    assert not quote_on_page("average annual turnover of at least Rs. 15 Crore", PAGE)


def test_too_short_quote_is_rejected_even_if_present():
    assert not quote_on_page("Section 5", PAGE)


def test_normalise_collapses_whitespace():
    assert normalise("  A\n\tB   C ") == "a b c"
