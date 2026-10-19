import pytest

from sema.normalize import int_to_words, normalize, ordinal_words, year_words

CASES = [
    ("It costs $12.50 today.", "It costs twelve dollars and fifty cents today."),
    ("Revenue hit $1.5M in Q3.", "Revenue hit one point five million dollars in Q three."),
    ("A $1 coffee.", "A one dollar coffee."),
    ("Pay €250 now", "Pay two hundred fifty euros now"),
    ("We raised £3bn.", "We raised three billion pounds."),
    ("Total: USD 1,200", "Total: one thousand two hundred US dollars"),
    ("Growth was 4.5%.", "Growth was four point five percent."),
    ("Meet Dr. Smith on Main St. at 3:30 PM.", "Meet Doctor Smith on Main Street at three thirty PM."),
    ("Flights to St. Louis", "Flights to Saint Louis"),
    ("Call at 9am", "Call at nine AM"),
    ("Due 10/18/2026", "Due October eighteenth, twenty twenty-six"),
    ("Released 2026-10-18.", "Released October eighteenth, twenty twenty-six."),
    ("On Oct. 3, 2025 we left.", "On October third, twenty twenty-five we left."),
    ("Born 4 July 1990", "Born the fourth of July, nineteen ninety"),
    ("In 1999 and 2005 and 2026", "In nineteen ninety-nine and two thousand five and twenty twenty-six"),
    ("The 1990s were wild", "The nineteen nineties were wild"),
    ("She finished 1st and 22nd.", "She finished first and twenty-second."),
    ("Henry VIII and Elizabeth II", "Henry the eighth and Elizabeth the second"),
    ("World War II ended. See Chapter IV.", "World War two ended. See Chapter four."),
    ("Read pages 10-20, e.g. the intro.", "Read pages ten to twenty, for example, the intro."),
    ("From 2020-2024 sales grew", "From twenty twenty to twenty twenty-four sales grew"),
    ("It is 72°F outside", "It is seventy-two degrees Fahrenheit outside"),
    ("Drive 5 km at 60 mph", "Drive five kilometers at sixty miles per hour"),
    ("A 1 GB file and 16 GB of RAM", "A one gigabyte file and sixteen gigabytes of RAM"),
    ("Mix 1/2 cup and 3/4 tsp", "Mix one half cup and three quarters tsp"),
    ("Call (555) 123-4567", "Call five five five, one two three, four five six seven"),
    ("Email jane.doe@example.com", "Email jane dot doe at example dot com"),
    ("Visit https://www.example.com/path?q=1.", "Visit example dot com."),
    ("Update to v2.1 now", "Update to version two point one now"),
    ("1,234,567 people", "one million two hundred thirty-four thousand five hundred sixty-seven people"),
    ("Pi is 3.14", "Pi is three point one four"),
    ("Tom & Jerry", "Tom and Jerry"),
    ("Great!!! Really???", "Great! Really?"),
    ("Thanks 🙏 so much 🎉", "Thanks so much"),
    ("**Bold** and `code`", "Bold and code"),
    ("Keep COVID-19 and MP3 and 3D intact", "Keep COVID-19 and MP3 and 3D intact"),
    ("It was -5 degrees", "It was minus five degrees"),
    ("He said — quietly — no.", "He said, quietly, no."),
    ("THIS IS A VERY IMPORTANT NOTICE", "This is a very important notice"),
    ("The FBI and NASA met", "The FBI and NASA met"),
    ("Item #3 is ready", "Item number three is ready"),
    ("It's 10:00", "It's ten o'clock"),
]


@pytest.mark.parametrize("src,expected", CASES)
def test_normalize(src, expected):
    assert normalize(src, force_english=True) == expected


def test_dmy_dates():
    assert normalize("Due 18/10/2026", date_order="DMY", force_english=True) == "Due October eighteenth, twenty twenty-six"


def test_non_english_passthrough():
    src = "Le rendez-vous est à 15h, merci beaucoup pour votre aide."
    assert normalize(src) == src


def test_words():
    assert int_to_words(0) == "zero"
    assert int_to_words(105) == "one hundred five"
    assert int_to_words(2_000_001) == "two million one"
    assert ordinal_words(21) == "twenty-first"
    assert ordinal_words(100) == "one hundredth"
    assert ordinal_words(12) == "twelfth"
    assert year_words(1905) == "nineteen oh five"
    assert year_words(1900) == "nineteen hundred"
    assert year_words(2010) == "twenty ten"
