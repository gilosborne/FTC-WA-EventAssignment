import tempfile
import unittest
from pathlib import Path

from sorter import config

ROOT = Path(__file__).resolve().parent.parent


def write(text):
    path = Path(tempfile.mkdtemp()) / "sorter.toml"
    path.write_text(text)
    return path


NO_FLAGS = {k: None for k in config.DEFAULTS}


class ReadTest(unittest.TestCase):
    def test_reads_every_section(self):
        path = write('program = "FTC"\nstates = ["WA"]\n'
                     '[files]\nteams = "t.csv"\noutput = "o.csv"\n'
                     '[sorting]\nmethod = "largest"\nferry_wait = 45\n'
                     '[review]\nsmall_zip = 2\ntravel_minutes = 120\n')
        self.assertEqual(config.read(path), {
            "program": "FTC", "teams": "t.csv", "out": "o.csv", "method": "largest",
            "ferry_wait": 45, "small_zip": 2, "flag_over": 120})

    def test_unknown_setting_is_named(self):
        with self.assertRaisesRegex(config.ConfigError, "unknown setting 'review.small_zips'"):
            config.read(write("[review]\nsmall_zips = 2\n"))

    def test_wrong_type_is_named(self):
        with self.assertRaisesRegex(config.ConfigError, "'review.small_zip' has the wrong type"):
            config.read(write('[review]\nsmall_zip = "three"\n'))
        with self.assertRaisesRegex(config.ConfigError, "'sorting.ferry_wait' has the wrong type"):
            config.read(write("[sorting]\nferry_wait = true\n"))

    def test_bad_toml_is_reported(self):
        with self.assertRaises(config.ConfigError):
            config.read(write("program = FLL\n"))


class ResolveTest(unittest.TestCase):
    def test_flags_beat_file_beat_defaults(self):
        path = write('program = "FLL"\n[sorting]\nmethod = "regret"\n[review]\nsmall_zip = 2\n')
        settings, used = config.resolve(dict(NO_FLAGS, small_zip=5), path)
        self.assertEqual(used, path)
        self.assertEqual((settings["program"], settings["method"], settings["small_zip"],
                          settings["large_zip"]), ("FLL", "regret", 5, 30))

    def test_program_is_required_somewhere(self):
        with self.assertRaisesRegex(config.ConfigError, "program must be one of"):
            config.resolve(NO_FLAGS, write("[review]\nsmall_zip = 2\n"))

    def test_invalid_method(self):
        with self.assertRaisesRegex(config.ConfigError, "method must be one of"):
            config.resolve(NO_FLAGS, write('program = "FLL"\n[sorting]\nmethod = "fastest"\n'))

    def test_explicit_missing_file_is_an_error(self):
        with self.assertRaisesRegex(config.ConfigError, "config file not found"):
            config.resolve(NO_FLAGS, Path("/nonexistent/sorter.toml"))

    def test_committed_sorter_toml_is_valid(self):
        settings = config.read(ROOT / "sorter.toml")
        self.assertIn(settings.get("program"), config.PROGRAMS)


if __name__ == "__main__":
    unittest.main()
