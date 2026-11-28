# External datasets

All free to use. None of them is committed to this repo: `python scripts/fetch_datasets.py` downloads them to `data/external/`, which is git-ignored.

| Dataset | What it is | Licence | Used for | Size here |
|---|---|---|---|---|
| [FLEURS](https://huggingface.co/datasets/google/fleurs) (Google) | Read speech with human transcripts, 102 languages; `de_de` and `en_us` used | CC BY 4.0 | **Day 7:** STT word error rate and language-ID accuracy on real human voices, on a standard benchmark that others publish numbers for. It complements the 60 own shop-floor recordings (domain vocabulary). | 50 clips per language from the `test` split (~74 MB); `--fleurs-n` for more |
| [AI4I 2020 Predictive Maintenance](https://archive.ics.uci.edu/dataset/601) (UCI) | 10,000 synthetic machine records: air/process temperature, speed, torque, tool wear, five failure modes (tool wear, heat dissipation, power, overstrain, random) | CC BY 4.0 | **Optional:** realistic sensor values behind a `get_machine_telemetry` tool, plus alarm texts modeled on its failure modes | 512 KB CSV |
| [MUSAN](https://www.openslr.org/17) (OpenSLR) | 6 h of noise (plus music and speech) | CC BY 4.0 (per-file licences inside) | **Optional, Day 8:** robustness test that mixes noise into the test clips at 10/5/0 dB SNR and reports WER under noise. Not downloaded by default (11 GB archive). | – |
| [Piper voices](https://huggingface.co/rhasspy/piper-voices) | Pretrained TTS voices | per voice, see each `MODEL_CARD` | **Day 4:** `de_DE-thorsten-medium` (Thorsten-Voice dataset, CC0) and `en_US-ljspeech-medium` (LJ Speech dataset, public domain). `en_US-lessac` was not used: its model card links to the Blizzard 2013 licence instead of stating one. Downloaded on first use to `models/piper/` (git-ignored). | ~63 MB per voice |

## Attribution

- **FLEURS:** Conneau, A. et al. (2022). *FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech.* arXiv:2205.12446. Licensed CC BY 4.0.
- **AI4I 2020:** Matzka, S. (2020). *AI4I 2020 Predictive Maintenance Dataset.* UCI Machine Learning Repository. https://doi.org/10.24432/C5HS5C. Licensed CC BY 4.0.
- **MUSAN** (if used): Snyder, D., Chen, G., Povey, D. (2015). *MUSAN: A Music, Speech, and Noise Corpus.* arXiv:1510.08484.

## Notes

- FLEURS audio is 16 kHz **32-bit float** WAV. `pipeline/stt.py:load_audio` reads it without extra dependencies.
- The FLEURS fetch streams the split's `.tar.gz` and stops after N clips, so it doesn't download the full 570 MB archive.
- FLEURS sentences come from Wikipedia (general vocabulary), while the own test set uses shop-floor vocabulary (machine names, alarm codes). Reporting both separates "how good is STT in general" from "how good is it on our domain".
