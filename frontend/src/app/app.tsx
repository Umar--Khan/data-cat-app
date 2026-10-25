export function App() {
  return (
    <>
      <a
        href="#datasets-heading"
        className="sr-only rounded-md bg-surface text-sm font-medium shadow-lg focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:px-3 focus:py-2"
      >
        Skip to datasets
      </a>
      <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        <header>
          <h1 className="text-2xl font-semibold">Data Catalogue</h1>
          <p className="mt-1 text-fg-muted">
            Register a dataset to get tags and a one-sentence summary.
          </p>
        </header>
        <main className="mt-8 space-y-8">
          <section aria-labelledby="add-dataset-heading">
            <h2 id="add-dataset-heading" className="text-lg font-semibold">
              Add a dataset
            </h2>
          </section>
          <section aria-labelledby="datasets-heading">
            <h2 id="datasets-heading" tabIndex={-1} className="text-lg font-semibold">
              Datasets
            </h2>
          </section>
        </main>
      </div>
    </>
  )
}
