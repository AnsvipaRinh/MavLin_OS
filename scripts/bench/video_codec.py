#!/usr/bin/env python3
"""
scripts/bench/video_codec.py - Video codec benchmark for Mavericks Linux

Phase A harness for host-relative video decode measurements.
Creates deterministic fixtures and measures decode performance.

Usage:
  python3 scripts/bench/video_codec.py --all                     # run everything
  python3 scripts/bench/video_codec.py --generate --force         # regenerate fixtures
  python3 scripts/bench/video_codec.py --bench --output /path/file.json
  python3 scripts/bench/video_codec.py --bench --output scripts/bench/results/video-codecs.json
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from collections import defaultdict

try:
    import psutil
except ImportError:
    psutil = None

REPO = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = Path("/tmp/mv-bench/codec")
RESULTS_DIR = REPO / "docs/benchmarks"

# Verified codecs and parameters from commit 406cb12
CODEC_CONFIGS = {
    "h264": {
        "encoder": "libx264",
        "preset": "veryfast",
        "crf": 23,
        "name": "libx264"
    },
    "vp9": {
        "encoder": "libvpx-vp9",
        "cpu_used": 2,
        "crf": 30,
        "name": "libvpx-vp9"
    },
    "hevc": {
        "encoder": "libx265",
        "preset": "veryfast",
        "crf": 26,
        "name": "libx265"
    },
    "av1_svt": {
        "encoder": "libsvtav1",
        "preset": 12,
        "crf": 30,
        "name": "libsvtav1"
    },
    "av1_aom": {
        "encoder": "libaom-av1",
        "cpu_used": 8,
        "crf": 30,
        "name": "libaom-av1"
    }
}

RESOLUTIONS = [
    ("720p", "1280x720"),
    ("1080p", "1920x1080")
]

FIXTURE_SPECS = {
    "frames": 120,
    "fps": 24,
    "duration_sec": 5.0
}

# Fallback frame counts for encodes too slow on the build host (2 threads).
# Key: codec_key_res_name -> frame count. Applied at fixture generation.
FRAME_FALLBACK = {}


def log(msg):
    print(f"[video_codec] {msg}", flush=True)


def _vainfo_probe():
    """Probe VA-API capability on this machine. Returns dict with status."""
    import shutil as _sh
    if not _sh.which("vainfo"):
        return {"vainfo_present": False, "status": "HW-ONLY: vainfo not installed on host"}
    try:
        r = subprocess.run(["vainfo"], capture_output=True, text=True, timeout=15)
        out = r.stdout + r.stderr
        profiles = [l.strip() for l in out.splitlines() if "VAProfile" in l]
        if r.returncode == 0 and profiles:
            return {"vainfo_present": True, "status": "driver present", "profiles": profiles[:8]}
        return {"vainfo_present": True, "status": "no usable VA driver on host (expected pre-hardware)",
                "raw_head": out[:200]}
    except Exception as e:
        return {"vainfo_present": True, "status": f"probe error: {e}"}


def get_host_cpu_model():
    try:
        with open("/proc/cpuinfo", "r", errors="replace") as f:
            for line in f:
                if "model name" in line:
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "unknown"


def get_ffmpeg_version():
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], 
            capture_output=True, text=True
        )
        first_line = result.stdout.split("\n")[0]
        version_match = re.search(r"ffmpeg version (\d+\.\d+\.\d+)", first_line)
        return version_match.group(1) if version_match else "unknown"
    except Exception:
        return "unknown"


def encode_video(fixture_path, width, height, codec, config, frames=None):
    """Encode video using specified codec and configuration"""
    fps = FIXTURE_SPECS["fps"]
    if frames is None:
        frames = FIXTURE_SPECS["frames"]
    duration = frames / fps

    # Build ffmpeg command
    cmd = [
        "ffmpeg", "-hide_banner",
        "-y", "-threads", "2",
        "-f", "lavfi", "-i", f"testsrc2=size={width}x{height}:rate={fps}:duration={duration}",
        "-c:v", config["encoder"]
    ]
    
    # Add codec-specific options
    if codec == "h264":
        cmd.extend(["-preset", config["preset"], "-crf", str(config["crf"])])
    elif codec == "vp9":
        cmd.extend(["-cpu-used", str(config["cpu_used"]) if "cpu_used" in config else "2",
                    "-crf", str(config["crf"]), "-b:v", "0"])
    elif codec == "hevc":
        cmd.extend(["-preset", config["preset"], "-crf", str(config["crf"])])
    elif codec == "av1_svt":
        cmd.extend(["-preset", str(config["preset"]), "-crf", str(config["crf"]),
                    "-pix_fmt", "yuv420p"])
    elif codec == "av1_aom":
        cmd.extend(["-cpu-used", str(config["cpu_used"]) if "cpu_used" in config else "8",
                    "-crf", str(config["crf"]), "-pix_fmt", "yuv420p"])
    
    cmd.extend([
        "-c:a", "aac",
        "-b:a", "128k",
        str(fixture_path)
    ])
    
    try:
        log(f"Encoding {width}x{height} {codec} ({config['name']}) -> {fixture_path.name}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log(f"Encoding failed: {result.stderr}")
            return False
        return True
    except Exception as e:
        log(f"Encoding error: {e}")
        return False


def generate_fixtures(force=False):
    """Generate video encoding fixtures for all codecs and resolutions"""
    if not force and any(FIXTURES_DIR.glob("*.mp4")):
        log(f"Fixtures already exist in {FIXTURES_DIR}, skipping (use --force to regenerate)")
        return
    
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Check for AV1 encoders availability
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders"], 
            capture_output=True, text=True
        )
        encoders_output = result.stdout
        
        has_svt = "svt_av1" in encoders_output or "libsvtav1" in encoders_output
        has_aom = "aom_av1" in encoders_output or "libaom-av1" in encoders_output
        
        log(f"AV1 encoder check: libsvtav1 available={has_svt}, libaom-av1 available={has_aom}")
        
        if has_svt:
            used_av1_config = "av1_svt"
            active_av1_name = "libsvtav1"
        elif has_aom:
            used_av1_config = "av1_aom"
            active_av1_name = "libaom-av1"
        else:
            log("WARNING: No AV1 encoders found, AV1 fixtures will be skipped")
            return
        
    except Exception as e:
        log(f"AV1 encoder check failed: {e}")
        return

    # Generate fixtures for each resolution
    for res_name, resolution in RESOLUTIONS:
        width, height = map(int, resolution.split("x"))
        log(f"\nGenerating fixtures for {res_name} ({resolution})")

        for codec_key, codec_config in CODEC_CONFIGS.items():
            if codec_key == "av1_svt" and not has_svt:
                continue
            if codec_key == "av1_aom" and not has_aom:
                continue
            if codec_key == "av1_svt" and has_svt:
                current_codec = "av1_svt"
                current_config = CODEC_CONFIGS[current_codec]
            elif codec_key == "av1_aom" and has_aom:
                current_codec = "av1_aom"
                current_config = CODEC_CONFIGS[current_codec]
            else:
                current_codec = codec_key
                current_config = codec_config

            fixture_path = FIXTURES_DIR / f"{codec_key}_{res_name}.mp4"
            frames = FRAME_FALLBACK.get(f"{codec_key}_{res_name}", FIXTURE_SPECS["frames"])

            if encode_video(fixture_path, width, height, current_codec, current_config, frames=frames):
                log(f"  Created {fixture_path.name}")
            else:
                log(f"  FAILED to create {fixture_path.name}")
    
    # Record which AV1 encoder was used
    fixture_meta = {
        "av1_encoder_used": active_av1_name,
        "has_svt": has_svt,
        "has_aom": has_aom,
        "resolution_variants": len(RESOLUTIONS),
        "codec_variants": list(CODEC_CONFIGS.keys()),
        "frames_default": FIXTURE_SPECS["frames"],
        "frame_fallbacks": FRAME_FALLBACK,
        "fixtures_dir": str(FIXTURES_DIR),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    meta_file = FIXTURES_DIR / "fixture_meta.json"
    with open(meta_file, "w") as f:
        json.dump(fixture_meta, f, indent=2)
    
    log(f"\nFixtures generated and metadata saved to {meta_file}")


def parse_ffmpeg_progress(output):
    """Parse ffmpeg -progress pipe:1 output: returns (last_frame, last_fps)"""
    last_frame = 0
    last_fps = 0.0
    for line in output.split("\n"):
        m = re.match(r"frame=(\d+)", line)
        if m:
            last_frame = int(m.group(1))
        m = re.match(r"fps=([\d.]+)", line)
        if m:
            try:
                last_fps = float(m.group(1))
            except ValueError:
                pass
    return last_frame, last_fps


def measure_decode(fixture_path, repeats=3):
    """Measure decode performance for a single fixture"""
    log(f"  Measuring decode: {fixture_path.name} (repeats={repeats})")

    decode_times = []
    cpu_usages = []
    peak_rss_list = []
    frames_counts = []
    ffmpeg_fps_list = []
    teardown_times = []
    dropped_proxies = []

    clip_fps = FIXTURE_SPECS["fps"]
    deadline_ms = 1000.0 / clip_fps

    for i in range(repeats):
        log(f"    Repeat {i+1}/{repeats}")

        cmd = [
            "ffmpeg", "-v", "info", "-benchmark",
            "-progress", "pipe:1", "-nostats",
            "-i", str(fixture_path),
            "-f", "null", "-"
        ]

        start_wall = time.monotonic()

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True
            )

            ps_proc = None
            peak_rss = 0
            cpu_samples = []
            if psutil is not None:
                try:
                    ps_proc = psutil.Process(proc.pid)
                    ps_proc.cpu_percent(None)
                except Exception:
                    ps_proc = None

            stdout_lines = []
            while True:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                if line:
                    stdout_lines.append(line)
                    if ps_proc is not None:
                        try:
                            peak_rss = max(peak_rss, ps_proc.memory_info().rss)
                            cpu_samples.append(ps_proc.cpu_percent(None))
                        except Exception:
                            pass

            proc.wait()
            wall_time = time.monotonic() - start_wall

            stdout = "".join(stdout_lines)
            last_frame, last_fps = parse_ffmpeg_progress(stdout)
            if last_frame > 0 and wall_time > 0:
                last_fps = last_frame / wall_time

            cpu_percent = max(cpu_samples) if cpu_samples else 0.0

            decode_times.append(wall_time)
            cpu_usages.append(cpu_percent)
            peak_rss_list.append(peak_rss // 1024 if peak_rss else 0)
            frames_counts.append(last_frame)
            ffmpeg_fps_list.append(last_fps)

            teardown_times.append(0)

            if last_frame > 0 and wall_time > 0:
                per_frame_ms = (wall_time * 1000) / last_frame
                if per_frame_ms > deadline_ms:
                    dropped = int(last_frame * (1 - deadline_ms / per_frame_ms))
                else:
                    dropped = 0
                dropped_proxies.append(dropped)
            else:
                dropped_proxies.append(0)

        except Exception as e:
            log(f"    Error in repeat {i+1}: {e}")
            decode_times.append(0)
            cpu_usages.append(0)
            peak_rss_list.append(0)
            frames_counts.append(0)
            ffmpeg_fps_list.append(0)
            teardown_times.append(0)
            dropped_proxies.append(0)
    
    # Calculate median values
    def _median(vals):
        pos = sorted([v for v in vals if v > 0])
        return pos[len(pos) // 2] if pos else 0

    median_wall_s = _median(decode_times)
    median_cpu_s = _median(cpu_usages)
    median_rss_kb = _median(peak_rss_list)
    median_frames = _median(frames_counts)
    median_ffmpeg_fps = _median(ffmpeg_fps_list)

    return {
        "wall_s": median_wall_s,
        "cpu_pct": median_cpu_s,
        "rss_kb": median_rss_kb,
        "ffmpeg_fps": median_ffmpeg_fps,
        "repeats": repeats,
        "frames_measured": median_frames,
        "teardown_ms": _median(teardown_times),
        "dropped_proxy": _median(dropped_proxies),
        "deadline_ms": deadline_ms
    }


def run_benchmark(output_path):
    """Run benchmarks for all codec/resolution combinations"""
    log("Starting codec benchmark...")
    
    # Generate fixtures first
    generate_fixtures()
    
    # Load fixture metadata
    meta_file = FIXTURES_DIR / "fixture_meta.json"
    if meta_file.exists():
        with open(meta_file, "r") as f:
            fixture_meta = json.load(f)
    else:
        fixture_meta = {"error": "fixture_meta.json not found"}
    
    results = {
        "schema": 1,
        "benchmark": "video_codec",
        "host": {
            "cpu_model": get_host_cpu_model(),
            "ffmpeg_version": get_ffmpeg_version(),
            "platform": platform.platform(),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "fixture_meta": fixture_meta,
        "clips": [],
        "ranking": {}
    }
    
    # Test each fixture
    fixtures = list(FIXTURES_DIR.glob("*.mp4"))
    log(f"Found {len(fixtures)} fixtures to test")
    
    for fixture_path in sorted(fixtures):
        # Extract codec and resolution from filename
        filename = fixture_path.name
        stem = filename.replace(".mp4", "")

        # Normalize codec name
        if stem.startswith("av1"):
            codec = "av1"
        else:
            codec = stem.split("_")[0]

        # Normalize resolution
        if "1080p" in stem:
            resolution = "1080p"
        elif "720p" in stem:
            resolution = "720p"
        else:
            resolution = "unknown"

        # Measure decode performance
        clip_result = measure_decode(fixture_path)
        clip_result["codec"] = codec
        clip_result["resolution"] = resolution
        clip_result["fixture"] = filename

        results["clips"].append(clip_result)

        log(f"  Completed: {codec} {resolution} - wall: {clip_result['wall_s']:.3f}s")
    
    # Calculate derived metrics for all clips FIRST (ranking + feasibility need them)
    for clip in results["clips"]:
        if clip["frames_measured"] > 0:
            clip["cost_per_frame_ms"] = (clip["wall_s"] * 1000) / clip["frames_measured"]
        else:
            clip["cost_per_frame_ms"] = 0

    # Calculate ranking based on 1080p performance
    clips_1080p = [c for c in results["clips"] if c["resolution"] == "1080p"]

    # Deduplicate by codec (av1_svt vs av1_aom): keep lowest cost_per_frame per codec
    HW_CODECS = {"h264": True, "vp9": True, "hevc": True, "av1": False}
    by_codec = {}
    for c in clips_1080p:
        if c["codec"] not in by_codec or c["cost_per_frame_ms"] < by_codec[c["codec"]]["cost_per_frame_ms"]:
            by_codec[c["codec"]] = c
    # Rank: HW-decodable first (by SW cost as tiebreaker), non-HW (AV1) last resort
    hw_clips = sorted([c for c in by_codec.values() if HW_CODECS.get(c["codec"], False)],
                      key=lambda x: x["cost_per_frame_ms"])
    sw_clips = sorted([c for c in by_codec.values() if not HW_CODECS.get(c["codec"], False)],
                      key=lambda x: x["cost_per_frame_ms"])
    ranked = hw_clips + sw_clips

    for rank, clip in enumerate(ranked, 1):
        clip["rank"] = rank
        clip["hw_decode_gen95"] = HW_CODECS.get(clip["codec"], False)
        clip["tier"] = "host-SW MEASURABLE"
        cpf = clip.get("cost_per_frame_ms", 0)
        if clip["codec"] == "av1":
            clip["feasibility_1080p_core_m3"] = (
                f"AV1-1080p-SW expected-heavy (inference: no HW engine on Gen95, "
                f"SW cost {cpf:.2f} ms/frame is moderate but SW-only on target) — last resort only"
            )
        elif clip["hw_decode_gen95"]:
            clip["feasibility_1080p_core_m3"] = (
                f"{clip['codec'].upper()}-1080p: HW decode on HD615 (Gen95) — "
                f"preferred tier; SW fallback measurable ({cpf:.2f} ms/frame)"
            )
        else:
            clip["feasibility_1080p_core_m3"] = f"SW-only ({cpf:.2f} ms/frame)"

    results["ranking_1080p"] = ranked

    # Remove the old derived-metrics loop (now done above ranking)
    results["tiers"] = {
        "host_sw": "MEASURABLE (this run): full numbers + ordering across codecs",
        "vaapi_hw": "HW-ONLY: unmeasurable here (no GPU); validate on target via mpv --hwdec + intel-media-driver",
        "power_thermal": "HW-ONLY: unmeasurable here; needs MacBook10,1 power/thermal instrumentation"
    }
    results["vaapi_probe"] = _vainfo_probe()

    # Write results
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    log(f"Benchmark complete. Results written to {output_path}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Video codec benchmark for Mavericks Linux")
    parser.add_argument("--generate", action="store_true", help="Generate video fixtures")
    parser.add_argument("--bench", action="store_true", help="Run benchmarks")
    parser.add_argument("--all", action="store_true", help="Run all operations (default)")
    parser.add_argument("--output", default="scripts/bench/results/video-codecs.json",
                        help="Output JSON file path")
    parser.add_argument("--force", action="store_true", help="Force regeneration of fixtures")
    parser.add_argument("--repeats", type=int, default=3, help="Number of repeats for each measurement")
    parser.add_argument("--av1-1080-frames", type=int, default=None,
                        help="Fallback frame count for AV1 1080p fixtures (encode too slow on weak hosts)")

    args = parser.parse_args()

    if args.av1_1080_frames:
        FRAME_FALLBACK["av1_svt_1080p"] = args.av1_1080_frames
        FRAME_FALLBACK["av1_aom_1080p"] = args.av1_1080_frames
        log(f"AV1 1080p fallback: {args.av1_1080_frames} frames")

    if args.all or (not args.generate and not args.bench):
        args.generate = True
        args.bench = True

    if args.generate:
        generate_fixtures(force=args.force)

    if args.bench:
        run_benchmark(args.output)


if __name__ == "__main__":
    main()
