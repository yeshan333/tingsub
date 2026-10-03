// Progressive enhancement: content, links and both screenshots work without JS.
const samples = {
  en: {
    original: "Take your time along the coast. The next stop can wait.",
    zh: "沿着海岸慢慢走，下一站不必着急。",
  },
  ja: {
    original: "海沿いをゆっくり歩こう。次の目的地は、急がなくていい。",
    zh: "沿着海岸慢慢走，下一站不必着急。",
  },
};

const translated = document.querySelector(".caption-zh");
const original = document.querySelector(".caption-original");
const translation = document.querySelector("#translation");
function updateSample() {
  const language = document.querySelector(
    '[name="sample-language"]:checked',
  ).value;
  const sample = samples[language];
  const source = document.querySelector(".sample-source q");
  source.textContent = sample.original;
  source.lang = language;
  translated.hidden = !translation.checked;
  translated.textContent = sample.zh;
  // Japanese bilingual mode displays Chinese + English, just like the product.
  // Turning translation off shows the authored Japanese source text instead.
  original.textContent = translation.checked
    ? samples.en.original
    : sample.original;
  original.lang = translation.checked ? "en" : language;
}
document
  .querySelectorAll('[name="sample-language"], #translation')
  .forEach((input) => {
    input.addEventListener("change", updateSample);
  });
document.querySelector(".demo-controls").hidden = false;
updateSample();

const screens = document.querySelector(".screens");
function updateScreen() {
  const selected = document.querySelector('[name="screen"]:checked').value;
  screens.querySelectorAll("figure").forEach((figure) => {
    figure.hidden = figure.dataset.screen !== selected;
  });
}
document.querySelectorAll('[name="screen"]').forEach((input) => {
  input.addEventListener("change", updateScreen);
});
screens.classList.add("enhanced");
document.querySelector(".screen-controls").hidden = false;
updateScreen();
