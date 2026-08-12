"""Create a small, deterministic extracellular-electrophysiology NWB example."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pynwb import NWBHDF5IO, NWBFile
from pynwb.ecephys import ElectricalSeries
from pynwb.file import Subject


def build_demo_file(path: Path) -> None:
    """Write a synthetic four-channel CA1 recording with trial metadata."""

    nwbfile = NWBFile(
        session_description="Synthetic CA1 resting-state recording",
        identifier="metricproof-nwb-demo-ecephys-001",
        session_start_time=datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc),
        session_id="demo-ecephys-001",
        experimenter=["MetricProof-NWB example"],
        lab="Open neuroscience methods demo",
        institution="Synthetic research institute",
        experiment_description=(
            "Demonstrates a reproducible validation-evidence workflow without "
            "containing human or animal observations."
        ),
        keywords=["synthetic", "ecephys", "CA1", "reproducibility"],
    )
    nwbfile.subject = Subject(
        subject_id="synthetic-mouse-001",
        species="Mus musculus",
        sex="U",
        age="P90D",
        description="Synthetic subject; no biological observations are included.",
    )

    device = nwbfile.create_device(
        name="demo-probe",
        description="Four-channel silicon probe used for the synthetic example.",
        manufacturer="MetricProof-NWB example",
    )
    group = nwbfile.create_electrode_group(
        name="probe0",
        description="Four synthetic recording sites.",
        location="hippocampal CA1",
        device=device,
    )
    for channel in range(4):
        nwbfile.add_electrode(
            id=channel,
            x=0.0,
            y=float(channel * 20),
            z=0.0,
            imp=float("nan"),
            location="hippocampal CA1",
            filtering="0.1-300 Hz band-pass",
            group=group,
        )

    electrodes = nwbfile.create_electrode_table_region(
        region=[0, 1, 2, 3],
        description="All channels on probe0.",
    )
    sample_rate = 1_000.0
    time = np.arange(2_000, dtype=np.float32) / sample_rate
    data = np.stack(
        [
            50.0 * np.sin(2.0 * np.pi * frequency * time)
            for frequency in (8.0, 12.0, 30.0, 55.0)
        ],
        axis=1,
    ).astype(np.float32)
    nwbfile.add_acquisition(
        ElectricalSeries(
            name="raw_ecephys",
            description="Synthetic local field potential traces in microvolts.",
            data=data,
            electrodes=electrodes,
            starting_time=0.0,
            rate=sample_rate,
            conversion=1e-6,
        )
    )

    nwbfile.add_trial_column(
        name="condition",
        description="Experimental condition assigned to the interval.",
    )
    nwbfile.add_trial(start_time=0.25, stop_time=0.75, condition="baseline")
    nwbfile.add_trial(start_time=1.00, stop_time=1.50, condition="stimulation")

    path.parent.mkdir(parents=True, exist_ok=True)
    with NWBHDF5IO(path, "w") as io:
        io.write(nwbfile)


if __name__ == "__main__":
    output = Path(__file__).with_name("synthetic_ecephys_session.nwb")
    build_demo_file(output)
    print(f"Wrote {output}")
