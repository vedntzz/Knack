// The /events listener: a deny landing anywhere switches this tab to it.
const url = document.body.dataset.events;
if (url && "EventSource" in window) {
  new EventSource(url).addEventListener("deny", (event) => {
    const next = `/verdict/${event.data}`;
    if (location.pathname !== next) location.assign(next);
  });
}
