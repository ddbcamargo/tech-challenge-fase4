"""Curadoria multiclasse AudioSet e avaliação com fonte sintética isolada.

Não há WAVs do YouTube nestes testes. Dados CSV simulados usam o formato oficial.
"""

import io
import os
import json
import tempfile
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from fase4.infrastructure.datasets.catalog import OFFICIAL_FILES, prepare_datasets
from fase4.infrastructure.datasets.audioset_stratified import StratifiedAudioSetSamples
from fase4.infrastructure.datasets.audioset_fetch import AuthorizedAudioSetFetcher, resolve_ffmpeg_exe
from fase4.infrastructure.voice_model import IsolationForestVoiceModel, write_pcm16
from fase4.application.service import ApplicationService

CATEGORIES = {"Speech": "/m/09x0r", "Breathing": "/m/0abc1",
              "Cough": "/m/01b_21", "Wheeze": "/m/0abc2", "Silence": "/m/0abc3"}
LABELS = ("index,mid,display_name\n" + "".join(
    f"{index},{mid},{name}\n" for index, (name, mid) in enumerate(CATEGORIES.items()))).encode()
PSV = b"HR|O2Sat|SBP|DBP|Resp|Temp\n80|98|120|80|16|36.5\n"


def segments(prefix: str, count: int, repeated_id: str | None = None) -> bytes:
    lines = ["# created for tests", "# YTID, start_seconds, end_seconds, positive_labels"]
    if repeated_id:
        lines.append(f'{repeated_id}, 0.000, 10.000, "{CATEGORIES["Speech"]}"')
    for catidx, (cat, mid) in enumerate(CATEGORIES.items()):
        for index in range(count):
            video_id = f"{prefix}{catidx:02d}{index:08d}"
            # Um exemplo multilabel para testar a preferência por exclusivos.
            labels = mid + ("," + CATEGORIES["Breathing"] if cat == "Speech" and index == 0 else "")
            lines.append(f'{video_id}, 0.000, 10.000, "{labels}"')
    return ("\n".join(lines) + "\n").encode()


class StratifiedSamplesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.official = self.root / "official"
        self.workspace = self.root / "audioset"
        payload = {
            "p100679.psv": PSV,
            "class_labels_indices.csv": LABELS,
            "balanced_train_segments.csv": segments("b", 17),
            "eval_segments.csv": segments("e", 9, repeated_id="b0000000000"),
        }
        with patch("fase4.infrastructure.datasets.catalog.urlopen",
                   side_effect=lambda url, timeout=30: io.BytesIO(next(
                       payload[spec.name] for spec in OFFICIAL_FILES if spec.url == url))):
            report = prepare_datasets(self.official)
        self.assertTrue(report["ready"])
        self.samples = StratifiedAudioSetSamples(self.official, self.workspace)
        self.train_quotas = {"Speech": 12, "Breathing": 12, "Cough": 12,
                             "Wheeze": 12, "Silence": 6}
        self.eval_quotas = {name: 5 for name in CATEGORIES}

    def curate(self, seed=42):
        return self.samples.select(seed=seed, train_quotas=self.train_quotas,
                                   eval_quotas=self.eval_quotas)

    def wav(self, name="ten.wav", seed=42):
        path = self.root / name
        t = np.arange(16000 * 10) / 16000
        rng = np.random.default_rng(seed)
        samples = ((0.045 * np.sin(2 * np.pi * (155 + seed) * t) +
                    rng.normal(0, 0.002, t.size)) * 32767).astype(np.int16)
        write_pcm16(path, samples)
        return path

    def test_strata_have_requested_counts_and_distinct_youtube_ids(self):
        data = self.curate()
        self.assertTrue(data["ready"])
        self.assertFalse(data["source_verified"])
        self.assertEqual(data["selected"], 79)
        self.assertEqual(data["available"], 0)
        self.assertEqual(data["shortages"], [])
        self.assertEqual(len({row["youtube_id"] for row in data["items"]}), 79)
        self.assertEqual(len({row["id"] for row in data["items"]}), 79)
        splits = {key: {row["youtube_id"] for row in data["items"] if row["split"] == key}
                  for key in ("balanced_train", "eval")}
        self.assertFalse(splits["balanced_train"] & splits["eval"])
        for row in data["items"]:
            self.assertIn(row["category_mid"], row["label_ids"])
        self.assertEqual(sum(row["selected"] for row in data["by_category"]), 79)
        self.assertFalse(self.samples.clips_root.exists())

    def test_seed_reproducible_and_changes_selection(self):
        a = [x["id"] for x in self.curate(seed=12)["items"]]
        self.samples = StratifiedAudioSetSamples(self.official, self.root / "different")
        self.assertEqual(a, [x["id"] for x in self.curate(seed=12)["items"]])
        self.assertNotEqual(a, [x["id"] for x in self.curate(seed=13)["items"]])

    def test_shortage_report_does_not_invent_samples(self):
        data = self.samples.select(seed=42, train_quotas={"Speech": 99},
                                   eval_quotas={"Speech": 3})
        self.assertEqual(data["selected"], 20)  # 17 balanced + 3 eval
        self.assertEqual(data["shortages"][0]["requested"], 99)
        self.assertEqual(data["shortages"][0]["selected"], 17)

    def test_category_training_isolated_from_eval_and_silence(self):
        data = self.curate()
        speech = [row for row in data["items"] if row["split"] == "balanced_train"
                  and row["category"] == "Speech"]
        evalu = next(row for row in data["items"] if row["split"] == "eval" and row["category"] == "Speech")
        for idx, row in enumerate(speech):
            self.samples.import_clip(row["id"], self.wav(f"training-{idx}.wav", idx + 10))
        self.samples.import_clip(evalu["id"], self.wav("evaluation.wav", 43))
        paths, origin = self.samples.references("Speech", "balanced_train")
        self.assertEqual(len(paths), 12)
        self.assertTrue(all("balanced_train" in str(path) for path in paths))
        self.assertEqual(origin["label"], "Speech")
        self.assertEqual(origin["curation"], "stratified")
        model = IsolationForestVoiceModel(self.root / "models/voice.joblib")
        trained = model.train_from_audioset(paths, origin)
        self.assertEqual(trained["mode"], "audioset_speech_reference")
        eval_paths, eval_source = self.samples.references("Speech", "eval")
        self.assertEqual(len(eval_paths), 1)
        self.assertEqual(eval_source["split"], "eval")
        self.assertFalse(model.analyze(eval_paths[0])["clinical_assessment"])
        with self.assertRaisesRegex(ValueError, "Silence"):
            self.samples.references("Silence", "balanced_train")
        with self.assertRaisesRegex(ValueError, "Proveniência"):
            model.train_from_audioset(eval_paths * 12, eval_source)

    def test_cough_model_is_separate_and_eval_not_used_for_training(self):
        curated = self.curate()
        cough_train = [row for row in curated["items"] if row["split"] == "balanced_train"
                       and row["category"] == "Cough"]
        cough_eval = next(row for row in curated["items"] if row["split"] == "eval"
                          and row["category"] == "Cough")
        for idx, item in enumerate(cough_train):
            self.samples.import_clip(item["id"], self.wav(f"cough{idx}.wav", idx + 55))
        self.samples.import_clip(cough_eval["id"], self.wav("cough_eval.wav", 100))
        # A composição real diferencia o caminho do modelo para cada categoria.
        app = ApplicationService(None, None, None, None,
                                 voice_model=IsolationForestVoiceModel(self.root / "voice.joblib"),
                                 stratified_samples=self.samples)
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            model = app.audioset_train_category("Cough")
            self.assertTrue(model["ready"])
            self.assertEqual(model["mode"], "audioset_cough_acoustic_reference")
            self.assertTrue((self.root / "models/audioset_cough.joblib").is_file())
            self.assertFalse((self.root / "voice.joblib").exists())
            report = app.audioset_evaluate_category("Cough")
            self.assertEqual(report["samples"], 1)
            self.assertEqual(report["category"], "Cough")
            self.assertIn(report["model_outliers"], (0, 1))
            self.assertFalse(report["source_verified"])
            self.assertIn("NÃO", report["metric_note"])
        finally:
            os.chdir(previous)

    def test_import_tamper_and_existing_selection_protection(self):
        data = self.curate()
        first = data["items"][0]
        with self.assertRaisesRegex(ValueError, "não pertence"):
            self.samples.import_clip("aaaaaaaaaaa_000000_010000", self.wav())
        with self.assertRaisesRegex(ValueError, "Duração"):
            bad = self.root / "short.wav"
            write_pcm16(bad, np.zeros(16000 * 2, dtype=np.int16))
            self.samples.import_clip(first["id"], bad)
        self.samples.import_clip(first["id"], self.wav())
        with self.assertRaisesRegex(ValueError, "sobrescrito"):
            self.samples.import_clip(first["id"], self.wav())
        with self.assertRaisesRegex(ValueError, "possui WAVs"):
            self.curate()
        # CSV trocado após curadoria invalida o relatório.
        (self.official / "balanced_train_segments.csv").write_text("fraude", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "alterado"):
            self.samples.status()

    def test_authorized_fetch_dry_plan_and_guards(self):
        self.curate()
        fetcher = AuthorizedAudioSetFetcher(self.samples)
        plan = fetcher.plan("Speech", "balanced_train", 3)
        self.assertEqual(plan["selected"], 12)
        self.assertEqual(len(plan["candidates"]), 3)
        self.assertEqual(plan["already_imported"], 0)
        with self.assertRaisesRegex(ValueError, "Confirme direitos"):
            fetcher.fetch(limit=1)
        with self.assertRaisesRegex(ValueError, "autorização real"):
            fetcher.fetch(limit=1, confirm_rights=True)
        with self.assertRaisesRegex(ValueError, "limite"):
            fetcher.plan(limit=101)
        with self.assertRaisesRegex(ValueError, "Categoria"):
            fetcher.plan(category="Unknown")
        with self.assertRaisesRegex(ValueError, "Diretório"):
            fetcher.fetch(limit=1, confirm_rights=True, source_dir=self.root / "absent")

    def test_authorized_local_batch_resume_and_training(self):
        data = self.curate()
        speech = [row for row in data["items"] if row["split"] == "balanced_train"
                  and row["category"] == "Speech"]
        sources = self.root / "authorized_sources"
        sources.mkdir()
        for index, row in enumerate(speech):
            wav = self.wav(f"source-{index}.wav", seed=20 + index)
            shutil.copy2(wav, sources / f'{row["youtube_id"]}.wav')
        fetcher = AuthorizedAudioSetFetcher(self.samples)
        first = fetcher.fetch("Speech", limit=6, confirm_rights=True, source_dir=sources)
        self.assertEqual(first["downloaded"], 6)
        self.assertEqual(first["failed"], 0)
        self.assertEqual(self.samples.status()["available"], 6)
        second = fetcher.fetch("Speech", limit=12, confirm_rights=True, source_dir=sources)
        self.assertEqual(second["downloaded"], 6)
        self.assertEqual(second["attempted"], 6)
        self.assertEqual(self.samples.status()["available"], 12)
        audit = (self.workspace / "authorized_acquisitions.jsonl").read_text().splitlines()
        self.assertEqual(len(audit), 12)
        self.assertEqual(json.loads(audit[0])["mode"], "local_authorized")
        self.assertFalse(json.loads(audit[0])["source_verified"])
        paths, provenance = self.samples.references("Speech", "balanced_train")
        model = IsolationForestVoiceModel(self.root / "models/voice.joblib")
        result = model.train_from_audioset(paths, provenance)
        self.assertTrue(result["ready"])
        self.assertEqual(result["reference_count"], 12)
        self.assertEqual(fetcher.plan("Speech")["pending_total"], 0)

    def test_authorized_local_batch_reports_missing_sources_without_fabricating_data(self):
        self.curate()
        source_dir = self.root / "empty_sources"
        source_dir.mkdir()
        result = AuthorizedAudioSetFetcher(self.samples).fetch(
            "Cough", limit=2, confirm_rights=True, source_dir=source_dir)
        self.assertEqual(result["attempted"], 2)
        self.assertEqual(result["failed"], 2)
        self.assertEqual(result["downloaded"], 0)
        self.assertFalse(self.samples.clips_root.exists())

    def test_authorized_online_commands_are_interval_scoped_and_do_not_use_bypass(self):
        self.curate()
        fetcher = AuthorizedAudioSetFetcher(self.samples)
        sample = self.wav("authorized_preview.wav", seed=17)
        download_commands = []
        actual_run = AuthorizedAudioSetFetcher._run

        def fake_run(command, *, timeout, action):
            if "yt_dlp" in command:
                download_commands.append(command)
                self.assertIn("--download-sections", command)
                self.assertNotIn("--cookies", command)
                self.assertNotIn("--proxy", command)
                output = command[command.index("-o") + 1].replace("%(ext)s", "wav")
                shutil.copy2(sample, output)
                return None
            return actual_run(command, timeout=timeout, action=action)

        with patch("fase4.infrastructure.datasets.audioset_fetch.importlib.util.find_spec",
                   return_value=object()), patch.object(AuthorizedAudioSetFetcher, "_run", new=staticmethod(fake_run)):
            data = fetcher.fetch("Speech", limit=1, confirm_rights=True, youtube_permission=True)
        self.assertEqual(data["downloaded"], 1)
        self.assertEqual(len(download_commands), 1)
        self.assertEqual(data["mode"], "youtube_authorized")
        self.assertIn("*0.0-10.0", download_commands[0])

    def test_resolve_ffmpeg_without_system_path(self):
        with patch("fase4.infrastructure.datasets.audioset_fetch.shutil.which", return_value=None):
            binary = resolve_ffmpeg_exe()
        self.assertTrue(Path(binary).is_file())
        self.assertIn("ffmpeg", Path(binary).name.lower())

    def test_yt_dlp_receives_explicit_ffmpeg_location(self):
        self.curate()
        fetcher = AuthorizedAudioSetFetcher(self.samples)
        sample = self.wav("sample_location.wav", seed=19)
        calls = []
        actual_run = AuthorizedAudioSetFetcher._run

        def fake_run(command, *, timeout, action):
            if "yt_dlp" in command:
                calls.append(command)
                output = command[command.index("-o") + 1].replace("%(ext)s", "wav")
                shutil.copy2(sample, output)
                return
            return actual_run(command, timeout=timeout, action=action)

        with patch("fase4.infrastructure.datasets.audioset_fetch.importlib.util.find_spec", return_value=object()), \
             patch.object(AuthorizedAudioSetFetcher, "_run", new=staticmethod(fake_run)):
            data = fetcher.fetch("Speech", limit=1, confirm_rights=True, youtube_permission=True)
        self.assertEqual(data["downloaded"], 1)
        cmd = calls[0]
        self.assertIn("--ffmpeg-location", cmd)
        self.assertEqual(cmd[cmd.index("--ffmpeg-location") + 1], resolve_ffmpeg_exe())

    def test_fails_on_invalid_category_and_seed(self):
        with self.assertRaisesRegex(ValueError, "Cotas"):
            self.samples.select(train_quotas={"Unknown": 12})
        with self.assertRaisesRegex(ValueError, "semente"):
            self.samples.select(seed=-1)


if __name__ == "__main__":
    unittest.main()
