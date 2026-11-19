# RGB MoCap - One-Click Installer (PixelArtistry)

Runs [RGB MoCap](https://github.com/toyxyz/toyxyz_RGBMocap) by toyxyz locally on your own PC: **a normal video in, 3D motion capture out.** No suit, no trackers, no subscription. It tracks one or several people, locks the feet to the ground, retargets the motion onto your own character (Mixamo FBX, VRM, PMX) and exports FBX, BVH or a Blender project.

This repo does not contain RGB MoCap. It is a small installer that sets everything up for you, downloads the ~25 GB of public model files, and imports the few files you have to register for.

## What you need

- Windows 10/11, 64-bit
- An NVIDIA GPU with a current driver (no AMD, no Mac, no Linux - that is an upstream limit)
- About **65 GB** of free disk space
- Three free accounts for the registered model files (see [step 2](#2-get-the-registered-files))

## Install

### 1. Run the installer

1. On this page: **Code → Download ZIP**, and unzip it on a drive with 65 GB free. Use a short path such as `D:\AI\RGBMoCap`.
2. Double-click `Install_RGBMoCap.bat`.
3. Let it run. It downloads about 33 GB and needs no input. How long it takes depends on your internet connection.

At the end it prints a **Result** list that tells you which motion models are ready and which files are still missing.

### 2. Get the registered files

A few files belong to research institutes that only hand them out after you sign up and accept their terms. Nobody is allowed to pass them on, so no installer can skip this. It is free and takes a few minutes.

> [!TIP]
> Do this first, while the installer is running. Hugging Face access can take a few minutes up to a few hours.

| Where | What to download | Needed for |
| --- | --- | --- |
| [smpl-x.is.tue.mpg.de](https://smpl-x.is.tue.mpg.de/download.php) | **Download SMPL-X v1.1 (NPZ+PKL, 830 MB)** → `models_smplx_v1_1.zip` | ExMR, GVHMR |
| [mano.is.tue.mpg.de](https://mano.is.tue.mpg.de/download.php) | **Models & Code** → `mano_v1_2.zip` | ExMR, GVHMR fingers |
| [mano.is.tue.mpg.de](https://mano.is.tue.mpg.de/download.php) | **Extended SMPL+H model (used in AMASS project)** → `smplh.tar.xz` | FlowHMR |
| [huggingface.co/facebook/sam-3d-body-dinov3](https://huggingface.co/facebook/sam-3d-body-dinov3) | `model.ckpt`, `model_config.yaml`, `assets/mhr_model.pt` | ExMR, FlowHMR |
| [huggingface.co/facebook/VGGT-Omega](https://huggingface.co/facebook/VGGT-Omega) | `vggt_omega_1b_512.pt` (optional) | FlowHMR with a moving camera |

### 3. Import them

1. Put the downloaded files into the `gated_downloads` folder next to the installer. You can also just leave them in your Windows Downloads folder. **Do not unpack the ZIP and TAR.XZ files**, the importer takes out what it needs.
2. Double-click `Import_Models.bat`.

The importer checks every file. A wrong version is rejected with a message instead of breaking the app. You can run it as often as you like, for example once per file as your access requests come through.

**Shortcut for the Hugging Face files:** if you are logged in with the Hugging Face CLI (`hf auth login`) or have `HF_TOKEN` set, `Import_Models.bat` downloads the SAM 3D Body and VGGT-Omega files for you as soon as your access is granted.

### 4. Start

Double-click `Run_RGBMoCap.bat`. Keep the black console window open while you use the app.

## Your first capture

1. Pick the **AI Motion Model** (ExMR is the default) and drop a video into the window, or use **File → Open Video**.
2. Optional: trim the clip by dragging the ends of the **Video** track in the timeline.
3. Click **Find person** and tick who you want to capture.
4. Click **Reconstruct 3D** and wait.
5. Check the result with the **Bone Overlay**. **Motion Correction** with *Foot* is on by default and reduces foot sliding (*Flat Ground* for level floors, *Multi Level* for stairs and slopes). Change settings or contact timings, then click **Apply Correction** - this does not run the AI again.
6. **File → Export...** saves FBX, BVH or a Blender project.

### Onto your own character

1. **File → Import Character...** and pick a **Mixamo FBX**, **VRM** or **PMX** character.
2. Right-click the character → **Retarget → [the captured person]**.
3. Right-click it again → **Export Character...** (FBX with or without mesh).

Custom bone mapping is not available yet, so a character from another tool has to go through the Mixamo auto-rigger first (upload it at [mixamo.com](https://www.mixamo.com), download it as FBX in T-pose with skin).

### Which model?

These are toyxyz's own impressions, not benchmarks:

| Model | Good for |
| --- | --- |
| **ExMR** | The default. Fast, good quality, fingers included, static or moving camera. |
| **FlowHMR** | Slower, best overall quality, fingers included. |
| **GVHMR** | Less consistent, but sometimes better for unusual poses such as backflips. |

### Optional: GEM-X, the model without a research-only licence

ExMR, FlowHMR and GVHMR are for learning, hobby and research use (see [License](#license)). **GEM-X** by NVIDIA is the one motion model in RGB MoCap that does not depend on them or on the SMPL body models: its code is Apache-2.0, its model uses the NVIDIA Open Model License and its SOMA body model is Apache-2.0. It needs **no registration**.

The trade-off, in toyxyz's words: fast, with relatively low overall motion quality. It captures one person from a fixed camera, in clips of up to 60 seconds.

1. Install RGB MoCap first (steps above), and close the app.
2. Double-click `Install_GEMX.bat`. It shows the links to the terms and asks you to confirm, then installs the add-on and its nine model files (about 10 GB in total, NVIDIA driver 580 or newer).
3. Start RGB MoCap and pick **GEM-X** under **AI Motion Model**.

Read the terms yourself before you rely on GEM-X for paid work. The person detector it uses has its own terms.

### Low VRAM

Leave **Resource Mode** on *Automatic*. With little free VRAM it switches to the *Low Memory* path on its own, which moves work to the CPU: slower, more system RAM, same quality. toyxyz measured 5.68 → 3.87 GiB for ExMR and 6.10 → 2.77 GiB for FlowHMR on short clips. Those are measurements on one PC, not guaranteed minimums.

## What the installer does

- Checks for 64-bit Windows, an NVIDIA GPU and enough disk space before it downloads anything.
- Downloads RGB MoCap (with git if you have it, otherwise as a ZIP).
- Fetches Blender and FFmpeg with Windows' own `curl` and checks them against the size and SHA-256 that RGB MoCap pins. This avoids the "certificate has expired" error the official installer runs into on PCs where Windows still caches an old Let's Encrypt certificate.
- Runs the official base install. It creates its own private Python runtimes plus Blender 4.5 and FFmpeg inside the `toyxyz_RGBMocap` folder. Nothing touches your system Python, ComfyUI or Blender.
- Downloads all public model files for ExMR, FlowHMR and GVHMR through RGB MoCap's own downloader, which verifies each file's size and SHA-256.
- Finds your registered files, unpacks the right file from each archive and imports it through RGB MoCap's own validated import.
- Writes `Run_RGBMoCap.bat` and `Update_RGBMoCap.bat`.
- Safe to re-run: everything that is finished is skipped. A log is written to `install_log.txt`.

Only want one model? Open a terminal in the folder and run `Install_RGBMoCap.bat --tools exmr` (or `exmr,flowhmr`).

## Notes

- **A download failed with a Google Drive message:** some files sit on Google Drive, which has a daily limit per file. Run `Import_Models.bat` again later, or open **Model Manager** inside the app and use **Manual Download... → Import...** for that row.
- **Updating:** close the app and run `Update_RGBMoCap.bat`. It needs [Git for Windows](https://git-scm.com/download/win) and only works if the installer downloaded RGB MoCap with git.
- **Not installed by this installer:** the optional MAMMA (multi-camera), PromptHMR and SAM 3.1 add-ons. They have their own `Setup_*.cmd` files inside `toyxyz_RGBMocap`, and MAMMA and PromptHMR need Visual Studio build tools and the CUDA Toolkit. See the [upstream model guides](https://github.com/toyxyz/toyxyz_RGBMocap/blob/main/docs/models/README.md).
- **Unreal Engine and MetaHuman:** RGB MoCap can stream motion straight onto a MetaHuman through Live Link. That needs Unreal Engine 5.7.4, Visual Studio 2022 with the C++ workload, `Setup_UnrealStream.cmd` inside `toyxyz_RGBMocap` and the MetaHuman Connect plugin. Follow the [upstream Unreal guide](https://github.com/toyxyz/toyxyz_RGBMocap/blob/main/docs/UNREAL_LIVE_LINK.md).
- **Moving the folder:** move the whole folder including `toyxyz_RGBMocap`. The models live in `toyxyz_RGBMocap\models`.

## License

> [!IMPORTANT]
> - **My files in this repo** (the installer scripts and this README): [MIT](LICENSE).
> - **RGB MoCap** (the app code): MIT, by [toyxyz](https://github.com/toyxyz/toyxyz_RGBMocap).
> - **The AI models and body models are not MIT.** GVHMR, ExMR and FootMR are for educational, research and nonprofit use. PromptHMR and MAMMA are non-commercial research only. SMPL, SMPL-X, SMPL-H and MANO have their own registered terms. The optional GEM-X add-on is the exception described [above](#optional-gem-x-the-model-without-a-research-only-licence). Read [THIRD_PARTY_NOTICES.md](https://github.com/toyxyz/toyxyz_RGBMocap/blob/main/THIRD_PARTY_NOTICES.md) before you use the results in a commercial project. This is not legal advice.

## Credits

All credit for RGB MoCap goes to [toyxyz](https://github.com/toyxyz/toyxyz_RGBMocap), and for the models to their authors: ExMR, FlowHMR, GVHMR, FootMR, HaMeR, HandFlow, SAM 3D Body, Sapiens, SMPL-X and MANO ([citations](https://github.com/toyxyz/toyxyz_RGBMocap/blob/main/docs/CITATIONS.md)). This repo only makes it easier to install.

## PixelArtistry

- YouTube: [youtube.com/@PixelArtistry_](https://www.youtube.com/@PixelArtistry_)
- FutureFrames newsletter: [go.pixel-artistry.com/newsletter](https://go.pixel-artistry.com/newsletter)
