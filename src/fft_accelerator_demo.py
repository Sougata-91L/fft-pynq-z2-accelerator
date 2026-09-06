"""
FFT Hardware Accelerator - PYNQ-Z2 Control Script
---------------------------------------------------
Consolidated from the project workflow described in the report:
"Design and Implementation of a High-Speed Fast Fourier Transform (FFT)
Hardware Accelerator on PYNQ-Z2 FPGA using Vivado Design Suite"

This script runs on the PYNQ-Z2 board (inside Jupyter Notebook) after the
Vivado bitstream (fft_8.bit) has been generated and copied to the board.
It loads the overlay, prepares an 8-point complex input signal, transfers
it to the FFT hardware accelerator via AXI DMA, and reads back the
frequency-domain output.

Requirements (on the PYNQ-Z2 board):
    - pynq
    - numpy
    - matplotlib
"""

import numpy as np
import matplotlib.pyplot as plt
from pynq import Overlay, allocate

# ---------------------------------------------------------------------------
# 1. Load the hardware overlay (bitstream) onto the FPGA
# ---------------------------------------------------------------------------
BITSTREAM = "fft_8.bit"
ol = Overlay(BITSTREAM)

# ---------------------------------------------------------------------------
# 2. Access the AXI DMA engine connected to the FFT IP core
# ---------------------------------------------------------------------------
data_channel = ol.fft_block.fft_dma
send_channel = data_channel.sendchannel
recv_channel = data_channel.recvchannel

# ---------------------------------------------------------------------------
# 3. Generate an 8-point complex input signal
# ---------------------------------------------------------------------------
SAMPLES = 8
T = 1
t = np.linspace(0, T, SAMPLES)

# Example input sequence (replace with your own signal of interest)
data = np.array([0, 1, 2, 2, 1, 0, 1, 2], dtype=np.csingle)

plt.figure()
plt.stem(t, data.real)
plt.title("Input Signal (Real Part)")
plt.xlabel("Time")
plt.ylabel("Amplitude")
plt.show()

# ---------------------------------------------------------------------------
# 4. Allocate physically-contiguous DMA buffers
# ---------------------------------------------------------------------------
input_buffer = allocate((SAMPLES,), np.csingle)
output_buffer = allocate((SAMPLES,), np.csingle)

# ---------------------------------------------------------------------------
# 5. Copy the input signal into the DMA input buffer
# ---------------------------------------------------------------------------
np.copyto(input_buffer, data)

# ---------------------------------------------------------------------------
# 6. Execute the FFT on hardware
# ---------------------------------------------------------------------------
send_channel.transfer(input_buffer)
recv_channel.transfer(output_buffer)
send_channel.wait()
recv_channel.wait()

print("FFT Hardware Output (frequency-domain coefficients):")
print(output_buffer)

# ---------------------------------------------------------------------------
# 7. (Optional) Verify against NumPy's FFT for a quick sanity check
#    The report verifies against MATLAB's fft() instead; NumPy is shown
#    here as a convenient software-only cross-check.
# ---------------------------------------------------------------------------
expected = np.fft.fft(data)
print("\nNumPy software FFT (reference):")
print(expected)

# ---------------------------------------------------------------------------
# 8. Clean up DMA buffers
# ---------------------------------------------------------------------------
input_buffer.close()
output_buffer.close()
