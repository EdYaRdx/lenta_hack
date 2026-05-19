import { useState } from "react";
import { startRun } from "./api/client";
import { TopBar } from "./components/TopBar";
import { ModeSelectionPage } from "./pages/ModeSelectionPage";
import { ProcessingPage } from "./pages/ProcessingPage";
import { ResultsPage } from "./pages/ResultsPage";
import { TrainingPage } from "./pages/TrainingPage";
import { UploadProcessingPage } from "./pages/UploadProcessingPage";
import { VideoUploadedPage } from "./pages/VideoUploadedPage";
import type { Department, Run } from "./types";

type Page = "mode" | "upload" | "uploaded" | "processing" | "results" | "training";

function App() {
  const [page, setPage] = useState<Page>("mode");
  const [department, setDepartment] = useState<Department>("wine/25_2-10");
  const [file, setFile] = useState<File | null>(null);
  const [run, setRun] = useState<Run | null>(null);

  const handleStartProcessing = async () => {
    const createdRun = await startRun({
      department,
      fileName: file?.name,
    });
    setRun(createdRun);
    setPage("processing");
  };

  return (
    <div className="app-shell">
      <TopBar onLogoClick={() => setPage("mode")} />
      <main className="page">
        {page === "mode" && (
          <ModeSelectionPage
            onProcessing={() => setPage("upload")}
            onTraining={() => setPage("training")}
          />
        )}

        {page === "upload" && (
          <UploadProcessingPage
            file={file}
            department={department}
            onBack={() => setPage("mode")}
            onContinue={() => setPage("uploaded")}
            onDepartmentChange={setDepartment}
            onFileChange={setFile}
          />
        )}

        {page === "uploaded" && (
          <VideoUploadedPage
            department={department}
            fileName={file?.name ?? "video.mp4"}
            onBack={() => setPage("upload")}
            onStart={handleStartProcessing}
          />
        )}

        {page === "processing" && run && (
          <ProcessingPage
            run={run}
            onComplete={() => setPage("results")}
            onRunUpdate={setRun}
          />
        )}

        {page === "results" && run && (
          <ResultsPage runId={run.id} onBack={() => setPage("mode")} />
        )}

        {page === "training" && <TrainingPage onBack={() => setPage("mode")} />}
      </main>
    </div>
  );
}

export default App;
