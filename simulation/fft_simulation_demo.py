"""
FFT Hardware Accelerator - OFFLINE SIMULATION
------------------------------------------------
This script lets you run and understand the exact same workflow as your
PYNQ-Z2 project (Overlay -> DMA buffers -> transfer -> FFT output ->
verification) WITHOUT needing the physical board.

Two things happen here:
  1. A from-scratch radix-2 Decimation-In-Time FFT is implemented, standing
     in for what the Xilinx FFT IP core does in hardware. Writing this
     yourself is what proves you understand the algorithm, not just the
     board plumbing.
  2. A "MockDMA" class mimics the PYNQ `allocate()` / sendchannel /
     recvchannel / wait() interface, so the control-flow code below reads
     almost identically to what runs on the actual board in Jupyter.

Run it with:
    python fft_simulation_demo.py
"""

import cmath
import numpy as np
import matplotlib.pyplot as plt


# ============================================================================
# 1. THE "HARDWARE" — a from-scratch radix-2 FFT (Cooley-Tukey, DIT)
# ============================================================================
def fft_radix2(x):
    """
    Recursive radix-2 Decimation-In-Time FFT.
    Requires len(x) to be a power of 2 (matches the 8-point IP core config
    used in the Vivado design).
    """
    n = len(x)
    if n & (n - 1) != 0:
        raise ValueError("Input length must be a power of 2 (e.g. 8, 16, 256)")
    if n == 1:
        return x

    even = fft_radix2(x[0::2])
    odd = fft_radix2(x[1::2])

    combined = [0] * n
    for k in range(n // 2):
        twiddle = cmath.exp(-2j * cmath.pi * k / n) * odd[k]
        combined[k] = even[k] + twiddle
        combined[k + n // 2] = even[k] - twiddle
    return combined


# ============================================================================
# 2. THE "BOARD INTERFACE" — mimics PYNQ's Overlay / DMA API
# ============================================================================
class MockDMA:
    """
    Stands in for `ol.fft_block.fft_dma` on the real PYNQ-Z2.
    Same method names (sendchannel, recvchannel, transfer, wait) so the
    control code below is a drop-in preview of the real board code.
    """
    def __init__(self):
        self.sendchannel = self
        self.recvchannel = self
        self._input = None
        self._output = None

    def transfer(self, buffer):
        # On real hardware this kicks off an AXI-DMA burst transfer.
        # Here we just remember which buffer is which.
        if self._input is None:
            self._input = buffer
        else:
            self._output = buffer

    def wait(self):
        # On real hardware this blocks until the DMA transfer completes.
        # Here, once both buffers are known, we "run" the FFT hardware.
        if self._output is not None and self._input is not None:
            result = fft_radix2(list(self._input))
            self._output[:] = result


class MockOverlay:
    """Stands in for `Overlay('fft_8.bit')`."""
    def __init__(self, bitstream_name):
        print(f"[MockOverlay] Pretending to load bitstream: {bitstream_name}")
        self.fft_block = type("Block", (), {"fft_dma": MockDMA()})()


def allocate(shape, dtype):
    """Stands in for `pynq.allocate()` — just a plain NumPy array here."""
    return np.zeros(shape, dtype=dtype)


# ============================================================================
# 3. YOUR ACTUAL CONTROL SCRIPT — identical structure to the PYNQ version
# ============================================================================
def run_fft_pipeline(data, label=""):
    SAMPLES = len(data)

    # Step 1: Load the overlay (mocked)
    ol = MockOverlay("fft_8.bit")

    # Step 2: Access the DMA engine
    data_channel = ol.fft_block.fft_dma
    send_channel = data_channel.sendchannel
    recv_channel = data_channel.recvchannel

    # Step 3: Allocate buffers
    input_buffer = allocate((SAMPLES,), np.csingle)
    output_buffer = allocate((SAMPLES,), np.csingle)

    # Step 4: Copy input data in
    np.copyto(input_buffer, data)

    # Step 5: Run the "hardware" FFT
    send_channel.transfer(input_buffer)
    recv_channel.transfer(output_buffer)
    send_channel.wait()
    recv_channel.wait()

    # Step 6: Reference check against NumPy's FFT (same role MATLAB played
    # in your report)
    reference = np.fft.fft(data)

    print(f"\n=== {label} (N={SAMPLES}) ===")
    print(f"{'Bin':<5}{'Hardware (sim) Output':<28}{'NumPy Reference':<28}Match?")
    for i in range(SAMPLES):
        hw = output_buffer[i]
        ref = reference[i]
        match = np.isclose(hw, ref, atol=1e-4)
        print(f"{i:<5}{str(np.round(hw, 4)):<28}{str(np.round(ref, 4)):<28}{match}")

    return output_buffer, reference


# ============================================================================
# 4. RUN IT — same 8-point sequence used in the project report
# ============================================================================
if __name__ == "__main__":
    data = np.array([0, 1, 2, 2, 1, 0, 1, 2], dtype=np.csingle)
    output_buffer, reference = run_fft_pipeline(data, label="Report input sequence")

    # DC bin sanity check (report calls out 9 + 0j)
    print(f"\nDC component (bin 0): {output_buffer[0]} "
          f"(expected: sum of inputs = {sum(data)})")

    # --- Plot input + magnitude spectrum ---
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))

    axes[0].stem(range(len(data)), data.real)
    axes[0].set_title("Input Signal (Time Domain)")
    axes[0].set_xlabel("Sample index")
    axes[0].set_ylabel("Amplitude")

    magnitude = np.abs(output_buffer)
    axes[1].stem(range(len(magnitude)), magnitude)
    axes[1].set_title("FFT Output Magnitude (Frequency Domain)")
    axes[1].set_xlabel("Frequency bin")
    axes[1].set_ylabel("|X[k]|")

    plt.tight_layout()
    plt.savefig("fft_simulation_result.png", dpi=150)
    print("\nSaved plot to fft_simulation_result.png")

    # --- Try a second, different signal to show it's general-purpose ---
    data2 = np.array([1, 0, -1, 0, 1, 0, -1, 0], dtype=np.csingle)  # a clean tone
    run_fft_pipeline(data2, label="Pure alternating tone")
