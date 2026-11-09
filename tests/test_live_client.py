import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))
import live_client  # noqa: E402

PLAYERS = [
    {"championName": "Ahri", "rawChampionName": "game_character_displayname_Ahri",
     "riotId": "Other#VN2", "riotIdGameName": "Other", "riotIdTagLine": "VN2"},
    {"championName": "Ngộ Không", "rawChampionName": "game_character_displayname_MonkeyKing",
     "riotId": "Player1#VN2", "riotIdGameName": "Player1", "riotIdTagLine": "VN2"},
]


def fake(responses):
    return lambda path: responses[path]


class CurrentGame(unittest.TestCase):
    def test_not_in_game_when_api_down(self):
        with mock.patch.object(live_client, "_get", side_effect=OSError("refused")):
            self.assertEqual(live_client.current_game(), {"in_game": False})

    def test_finds_my_champion_by_riot_id(self):
        r = {"/activeplayername": "Player1#VN2", "/playerlist": PLAYERS,
             "/gamestats": {"gameMode": "KIWI", "gameTime": 12.0}}
        with mock.patch.object(live_client, "_get", side_effect=fake(r)):
            g = live_client.current_game()
        self.assertTrue(g["in_game"])
        self.assertEqual(g["champion_raw"], "game_character_displayname_MonkeyKing")
        self.assertEqual(g["game_mode"], "KIWI")

    def test_matches_name_without_tag(self):
        r = {"/activeplayername": "Player1", "/playerlist": PLAYERS, "/gamestats": {}}
        with mock.patch.object(live_client, "_get", side_effect=fake(r)):
            self.assertEqual(live_client.current_game()["champion_name"], "Ngộ Không")


if __name__ == "__main__":
    unittest.main()
