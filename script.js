const storedTheme = localStorage.getItem("theme");
const preferredDark = window.matchMedia("(prefers-color-scheme: dark)").matches;

const applyTheme = (theme) => {
  document.documentElement.dataset.theme = theme;
};

applyTheme(storedTheme || (preferredDark ? "dark" : "light"));

const createDiaryCard = (entry) => {
  const link = document.createElement("a");
  link.className = "diary-card-link";
  link.href = entry.url || "#";

  const article = document.createElement("article");
  article.className = "diary-card";

  const head = document.createElement("div");
  head.className = "diary-head";

  const time = document.createElement("time");
  time.dateTime = entry.date || "";
  time.textContent = entry.displayDate || entry.date || "";

  const tag = document.createElement("span");
  tag.textContent = entry.tag || "Diary";

  head.append(time, tag);

  const title = document.createElement("h3");
  title.textContent = entry.title || "未命名日记";

  const summary = document.createElement("p");
  summary.textContent = entry.summary || "";

  const more = document.createElement("span");
  more.className = "diary-readmore";
  more.textContent = "阅读全文";

  article.append(head, title, summary, more);
  link.append(article);
  return link;
};

const renderDiaryEntries = (diaryList, entries) => {
  if (!diaryList) return;

  diaryList.innerHTML = "";

  if (!Array.isArray(entries) || entries.length === 0) {
    const empty = document.createElement("article");
    empty.className = "diary-card diary-empty";

    const title = document.createElement("h3");
    title.textContent = "还没有公开日记";

    const text = document.createElement("p");
    text.textContent =
      "把 OpenClaw 生成的日记放进 diary/entries 后，再运行同步脚本，这里就会自动显示最新内容。";

    empty.append(title, text);
    diaryList.append(empty);
    return;
  }

  entries.forEach((entry) => {
    diaryList.append(createDiaryCard(entry));
  });
};

const loadDiaryFeed = async (diaryList) => {
  if (!diaryList) return;

  try {
    const response = await fetch("./diary/index.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const entries = await response.json();
    renderDiaryEntries(diaryList, entries);
  } catch (error) {
    renderDiaryEntries(diaryList, []);
  }
};

const initReadingProgress = () => {
  const progressBar = document.querySelector("[data-reading-progress]");
  const article = document.querySelector(".entry-article");

  if (!progressBar || !article) return;

  const updateProgress = () => {
    const articleTop = article.offsetTop;
    const articleHeight = article.offsetHeight;
    const viewportHeight = window.innerHeight;
    const scrollTop = window.scrollY;
    const maxScrollable = Math.max(articleHeight - viewportHeight, 1);
    const rawProgress = ((scrollTop - articleTop) / maxScrollable) * 100;
    const progress = Math.min(100, Math.max(0, rawProgress));
    progressBar.style.transform = `scaleX(${progress / 100})`;
  };

  updateProgress();
  window.addEventListener("scroll", updateProgress, { passive: true });
  window.addEventListener("resize", updateProgress);
};

const initPage = () => {
  const themeToggle = document.querySelector(".theme-toggle");
  const diaryList = document.querySelector("#diary-list");

  themeToggle?.addEventListener("click", () => {
    const nextTheme =
      document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(nextTheme);
    localStorage.setItem("theme", nextTheme);
  });

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );

  document.querySelectorAll(".reveal").forEach((element) => observer.observe(element));

  loadDiaryFeed(diaryList);
  initReadingProgress();
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initPage, { once: true });
} else {
  initPage();
}
