import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
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

    def test_enemies_from_other_team(self):
        players = [
            {**PLAYERS[1], "team": "ORDER"},
            {**PLAYERS[0], "team": "CHAOS", "level": 7,
             "items": [{"itemID": 3165, "displayName": "Morello"}, {"itemID": 1001, "displayName": "Giày"}]},
            {"championName": "Ngộ Không 2", "rawChampionName": "game_character_displayname_DrMundo", "team": "CHAOS",
             "riotId": "X#1", "items": []},
            {"championName": "Đồng đội", "rawChampionName": "game_character_displayname_Lux", "team": "ORDER",
             "riotId": "Y#1"},
        ]
        r = {"/activeplayername": "Player1#VN2", "/playerlist": players, "/gamestats": {}}
        with mock.patch.object(live_client, "_get", side_effect=fake(r)):
            g = live_client.current_game()
        self.assertEqual(g["team"], "ORDER")
        self.assertEqual([e["slug"] for e in g["enemies"]], ["ahri", "drmundo"])
        self.assertEqual(g["enemies"][0]["items"], [3165, 1001])
        self.assertEqual(g["enemies"][0]["level"], 7)

    def test_matches_name_without_tag(self):
        r = {"/activeplayername": "Player1", "/playerlist": PLAYERS, "/gamestats": {}}
        with mock.patch.object(live_client, "_get", side_effect=fake(r)):
            self.assertEqual(live_client.current_game()["champion_name"], "Ngộ Không")


if __name__ == "__main__":
    unittest.main()
