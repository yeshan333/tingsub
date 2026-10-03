// The AudioContext performs band-limited sample-rate conversion to 16 kHz.
// Only bounded 20 ms PCM16 packets cross the audio thread; no codecs or base64.
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new ArrayBuffer(648);
    this.view = new DataView(this.buffer);
    this.offset = 0;
    this.port.onmessage = ({ data }) => {
      if (data.type === 'clock') this.epoch = data.epoch;
    };
  }
  process(inputs) {
    if (this.epoch === undefined) return true;
    const channels = inputs[0];
    // Missing input still advances the audio clock: emit silence at that time.
    const count = channels?.[0]?.length ?? 128;
    for (let i = 0; i < count; i++) {
      let value = 0;
      for (const channel of channels || []) value += channel[i];
      value = channels?.length ? Math.max(-1, Math.min(1, value / channels.length)) : 0;
      this.view.setInt16(8 + this.offset * 2, Math.round(value * (value < 0 ? 32768 : 32767)), true);
      if (++this.offset === 320) {
        // Timestamp the end of this packet in the host clock domain.
        this.view.setFloat64(0, (this.epoch ?? 0) + (currentTime + (i + 1) / sampleRate) * 1000, true);
        this.port.postMessage(this.buffer, [this.buffer]);
        this.buffer = new ArrayBuffer(648);
        this.view = new DataView(this.buffer);
        this.offset = 0;
      }
    }
    return true;
  }
}
registerProcessor('pcm16', PCMProcessor);
