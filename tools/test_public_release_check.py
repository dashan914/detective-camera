import json
import unittest
from public_release_check import ROOT, excluded, pending_reviews


class PublicPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy=json.loads((ROOT/'tools/release_policy.json').read_text())

    def test_current_audio_never_in_candidate_package(self):
        for name in ('demo/audio/clothes-case-clean.mp3','voice_pack_12/filesystem/voice/report.mp3',
                     'trial.mp3', 'TRIAL.MP3'):
            self.assertTrue(excluded(name,self.policy))

    def test_history_and_parent_paths_are_excluded(self):
        for name in ('.git/config','demo/.git/config','../outside.md','/outside.md'):
            self.assertTrue(excluded(name,self.policy))

    def test_pending_third_party_materials_are_excluded(self):
        for name in ('backend/poem_library.json','firmware/PoetryCameraDirector/es8311.cpp',
                     'firmware/PoetryCameraDirector/es8311.h'):
            self.assertTrue(excluded(name,self.policy))

    def test_private_runtime_and_device_images_are_excluded(self):
        for name in ('backend/.env','backend/director_state.json','firmware/flash.bin',
                     'private.pem', 'flash.bin', 'director_state.json', 'node_modules/pkg/index.js'):
            self.assertTrue(excluded(name,self.policy))

    def test_docs_and_geometry_remain_candidates(self):
        for name in ('LICENSE','README.md','hardware/stl/01_Front_fascia.stl','hardware/cad/DASHAN_V33.blend'):
            self.assertFalse(excluded(name,self.policy))

    def test_repository_publication_does_not_complete_asset_reviews(self):
        self.assertEqual(self.policy['mode'],'public_repository_with_unverified_asset_exceptions')
        self.assertIs(self.policy['publish_authorized'],True)
        self.assertTrue(pending_reviews(self.policy))


if __name__ == '__main__': unittest.main()
