"""Sea Cam: observation log for sea animals."""

from wildcam_core import AppConfig, run

CONFIG = AppConfig(
    title="Sea Cam Log",
    table="sea_observations",
    accent="#0d47a1",
    animal_hint="e.g. harbour seal, bottlenose dolphin",
)

if __name__ == "__main__":
    run(CONFIG)
