document.addEventListener("DOMContentLoaded", () => {
  const player = document.getElementById("playlist-player");
  if (!player) return;

  const links = Array.from(document.querySelectorAll("a[data-audio-url]"));
  const urls = links.map((link) => link.dataset.audioUrl || "");
  const initialUrl = player.dataset.initialUrl || "";
  let currentIndex = urls.indexOf(initialUrl);
  if (currentIndex === -1) {
    currentIndex = 0;
  }

  const setActiveLink = () => {
    links.forEach((link, idx) => {
      if (idx === currentIndex) {
        link.classList.add("active");
      } else {
        link.classList.remove("active");
      }
    });
  };

  if (
    (!player.getAttribute("src") || player.getAttribute("src") === "") &&
    urls.length
  ) {
    player.src = urls[currentIndex] || "";
  }
  setActiveLink();

  const updateCurrentIndex = (url) => {
    const idx = urls.indexOf(url);
    if (idx !== -1) {
      currentIndex = idx;
      setActiveLink();
    }
  };

  links.forEach((link, idx) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const url = link.dataset.audioUrl;
      if (!url) return;
      updateCurrentIndex(url);
      player.src = url;
      player.play().catch(() => {});
    });
  });

  player.addEventListener("ended", () => {
    if (urls.length === 0) return;
    const nextIndex = currentIndex + 1;
    if (nextIndex < urls.length) {
      currentIndex = nextIndex;
      const nextUrl = urls[currentIndex];
      if (nextUrl) {
        player.src = nextUrl;
        player.play().catch(() => {});
        setActiveLink();
      }
    }
  });
});
