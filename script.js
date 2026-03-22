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

  if (entry.coverImage) {
    article.classList.add("diary-card-has-cover");

    const media = document.createElement("div");
    media.className = "diary-card-media";

    const image = document.createElement("img");
    image.className = "diary-card-image";
    image.src = entry.coverImage;
    image.alt = `${entry.title || "日记"} 封面图`;
    image.loading = "lazy";

    media.append(image);
    article.append(media);
  }

  const body = document.createElement("div");
  body.className = "diary-card-body";

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

  body.append(head, title, summary, more);
  article.append(body);
  link.append(article);
  return link;
};

const getDiaryMonthKey = (entry) => {
  const rawDate = entry?.date || "";
  return rawDate.slice(0, 7).replace("-", ".");
};

const buildArchiveGroups = (entries) => {
  const groups = new Map();

  entries.forEach((entry) => {
    const month = getDiaryMonthKey(entry);
    if (!month) return;
    groups.set(month, (groups.get(month) || 0) + 1);
  });

  return Array.from(groups.entries()).map(([month, count]) => ({ month, count }));
};

const renderDiaryArchive = (archiveRoot, entries, activeMonth, onSelectMonth) => {
  if (!archiveRoot) return;

  archiveRoot.innerHTML = "";

  if (!Array.isArray(entries) || entries.length === 0) {
    return;
  }

  const buttons = [{ month: "all", count: entries.length, label: "全部" }, ...buildArchiveGroups(entries)];

  buttons.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "diary-archive-button";
    button.dataset.month = item.month;
    button.textContent =
      item.month === "all" ? `${item.label} · ${item.count}` : `${item.month} · ${item.count}`;

    if (item.month === activeMonth) {
      button.classList.add("is-active");
    }

    button.addEventListener("click", () => onSelectMonth(item.month));
    archiveRoot.append(button);
  });
};

const renderDiaryEntries = (diaryList, entries, activeMonth = "all") => {
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

  const filteredEntries =
    activeMonth === "all"
      ? entries
      : entries.filter((entry) => getDiaryMonthKey(entry) === activeMonth);

  if (filteredEntries.length === 0) {
    const empty = document.createElement("article");
    empty.className = "diary-card diary-empty";

    const title = document.createElement("h3");
    title.textContent = `${activeMonth} 暂时还没有公开日记`;

    const text = document.createElement("p");
    text.textContent = "切回“全部”或继续写下去，这里会慢慢长出你的归档。";

    empty.append(title, text);
    diaryList.append(empty);
    return;
  }

  filteredEntries.forEach((entry) => {
    diaryList.append(createDiaryCard(entry));
  });
};

const loadDiaryFeed = async (diaryList, archiveRoot) => {
  if (!diaryList) return;

  try {
    const response = await fetch(`./diary/index.json?ts=${Date.now()}`, {
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const entries = await response.json();

    const state = {
      entries,
      activeMonth: "all",
    };

    const rerender = () => {
      renderDiaryArchive(archiveRoot, state.entries, state.activeMonth, (month) => {
        state.activeMonth = month;
        rerender();
      });
      renderDiaryEntries(diaryList, state.entries, state.activeMonth);
    };

    rerender();
  } catch (error) {
    renderDiaryArchive(archiveRoot, [], "all", () => {});
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
  const diaryArchive = document.querySelector("#diary-archive");

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

  loadDiaryFeed(diaryList, diaryArchive);
  initReadingProgress();
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initPage, { once: true });
} else {
  initPage();
}
