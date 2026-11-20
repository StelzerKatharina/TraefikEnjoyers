"""Land & Air Cam: observation log for land- and air-based animals."""

from wildcam_core import AppConfig, run

CONFIG = AppConfig(
    title="Land & Air Cam Log",
    table="land_air_observations",
    accent="#2e7d32",
    animal_hint="e.g. red fox, golden eagle",
)

if __name__ == "__main__":
    run(CONFIG)
