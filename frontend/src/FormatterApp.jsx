import { useEffect, useMemo, useRef, useState } from "react";
import DocumentInputPanel from "./components/DocumentInputPanel";
import HeroSection from "./components/HeroSection";
import HowItWorks from "./components/HowItWorks";
import PaperSetupPanel from "./components/PaperSetupPanel";
import {
  AuthSessionError,
  authenticatedFetch,
  downloadAuthenticatedFile,
} from "./utils/apiClient";
import {
  getFormattingScoreLabel,
  getFormattingScoreTone,
  normalizeAnalysisResponse,
  normalizeFixResponse,
} from "./utils/normalizeAnalysisResponse";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.PROD ? "" : "http://127.0.0.1:8000");

const MAX_FILE_SIZE = 10 * 1024 * 1024;

const TEMPLATE_OPTIONS = [
  {
    id: "apa7_student",
    label: "APA 7 Student Paper",
  },
];

const FIX_LABELS = {
  margins: "Document margins corrected",
  title_page_vertical_center: "Title page vertically centered",
  title_page_paragraphs_centered: "Title-page paragraphs centered",
  cover_page_leading_blanks_inserted: "Title-page spacing adjusted",
  introduction_page_break: "Introduction page break added",
  references_page_break: "References page break added",
  major_heading_spacing: "Major heading spacing corrected",
  empty_paragraphs_removed: "Unnecessary empty paragraphs removed",
  bullet_only_paragraphs_removed: "Invalid bullet-only paragraphs removed",
  intro_leading_junk_removed: "Unnecessary content before introduction removed",
  tables_touched: "Tables formatted",
  table_caption_paragraphs_touched: "Table captions formatted",
  table_title_paragraphs_touched: "Table titles formatted",
  body_paragraphs_touched: "Body paragraphs formatted",
  paragraph_indent: "Paragraph indentation corrected",
  line_spacing: "Line spacing corrected",
  space_before: "Spacing before paragraphs corrected",
  space_after: "Spacing after paragraphs corrected",
  font_name: "Font styles corrected",
  font_size: "Font sizes corrected",
  reference_entries_touched: "Reference entries formatted",
  reference_entries_rebuilt: "Reference entries rebuilt",
  reference_hanging_indent: "Reference hanging indents corrected",
  reference_line_spacing: "Reference line spacing corrected",
  reference_space_before: "Reference spacing before corrected",
  reference_space_after: "Reference spacing after corrected",
  headings_touched: "Headings formatted",
  text_normalized: "Text inconsistencies normalized",
  safe_rules_applied: "Supported formatting rules applied",
};

function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 KB";

  const megabytes = bytes / (1024 * 1024);

  if (megabytes >= 1) {
    return `${megabytes.toFixed(2)} MB`;
  }

  return `${Math.ceil(bytes / 1024)} KB`;
}

function getFriendlyFixLabel(key) {
  if (FIX_LABELS[key]) {
    return FIX_LABELS[key];
  }

  return key
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function FormatterApp() {
  const fileInputRef = useRef(null);
  const workspaceRef = useRef(null);

  const [file, setFile] = useState(null);
  const [templateId, setTemplateId] = useState(TEMPLATE_OPTIONS[0].id);
  const [loadingAction, setLoadingAction] = useState("");
  const [analyzeResult, setAnalyzeResult] = useState(null);
  const [fixResult, setFixResult] = useState(null);
  const [error, setError] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [activeTab, setActiveTab] = useState("upload");

  const isLoading = Boolean(loadingAction);
  const hasWorkspaceContent = Boolean(
    file || analyzeResult || fixResult || loadingAction
  );

  useEffect(() => {
    if (analyzeResult || fixResult || loadingAction) {
      setActiveTab("preview");
    }
  }, [analyzeResult, fixResult, loadingAction]);

  const analysis = useMemo(
    () => (analyzeResult ? normalizeAnalysisResponse(analyzeResult) : null),
    [analyzeResult]
  );

  const fixModel = useMemo(
    () => (fixResult ? normalizeFixResponse(fixResult) : null),
    [fixResult]
  );

  const safeCount = analysis?.safeCount ?? 0;
  const score = analysis?.formattingScore ?? 0;
  const scoreLabel = getFormattingScoreLabel(score);
  const scoreTone = getFormattingScoreTone(score);

  const visibleFixedCounts = useMemo(() => {
    if (!fixResult?.fixed_counts) {
      return [];
    }

    return Object.entries(fixResult.fixed_counts)
      .filter(([, value]) => Number(value) > 0)
      .map(([key, value]) => ({
        key,
        value: Number(value),
        label: getFriendlyFixLabel(key),
      }));
  }, [fixResult]);

  const totalFixed = visibleFixedCounts.reduce(
    (total, item) => total + item.value,
    0
  );

  const resetResults = () => {
    setAnalyzeResult(null);
    setFixResult(null);
    setError("");
  };

  const resetWorkflow = () => {
    setFile(null);
    setAnalyzeResult(null);
    setFixResult(null);
    setError("");
    setLoadingAction("");
    setActiveTab("upload");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const selectFile = (selectedFile) => {
    if (!selectedFile) {
      return;
    }

    const isDocx = selectedFile.name.toLowerCase().endsWith(".docx");

    if (!isDocx) {
      setFile(null);
      resetResults();
      setError("Unsupported file type. Please upload a .docx file.");
      return;
    }

    if (selectedFile.size > MAX_FILE_SIZE) {
      setFile(null);
      resetResults();
      setError("This file is larger than 10 MB. Please choose a smaller file.");
      return;
    }

    setFile(selectedFile);
    resetResults();
    setActiveTab("upload");
  };

  const handleFileChange = (event) => {
    const selectedFile = event.target.files?.[0] || null;
    selectFile(selectedFile);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);

    const droppedFile = event.dataTransfer.files?.[0] || null;
    selectFile(droppedFile);
  };

  const handleTemplateChange = (event) => {
    setTemplateId(event.target.value);
    resetResults();
  };

  const scrollToWorkspace = () => {
    workspaceRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleAnalyze = async () => {
    if (!file) {
      setError("Please upload a Word document before continuing.");
      setActiveTab("upload");
      return;
    }

    setLoadingAction("analyze");
    setError("");
    // Replace stale analysis completely — do not append.
    setAnalyzeResult(null);
    setFixResult(null);
    setActiveTab("preview");

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("template_id", templateId);

      const response = await authenticatedFetch(
        `${API_BASE}/documents/analyze`,
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data?.detail
            ? typeof data.detail === "string"
              ? data.detail
              : JSON.stringify(data.detail)
            : `Analysis failed with status ${response.status}.`
        );
      }

      setAnalyzeResult(data);
    } catch (requestError) {
      setError(
        requestError instanceof AuthSessionError
          ? requestError.message
          : requestError.message ||
              "We could not analyze this document. Please try again."
      );
      setActiveTab("upload");
    } finally {
      setLoadingAction("");
    }
  };

  const handleFix = async () => {
    if (!file) {
      setError("Please upload a Word document before continuing.");
      setActiveTab("upload");
      return;
    }

    if (!analysis?.canFix) {
      setError("There are no formatting issues Forma APA can safely fix.");
      return;
    }

    setLoadingAction("fix");
    setError("");
    setFixResult(null);
    setActiveTab("preview");

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("template_id", templateId);

      const response = await authenticatedFetch(`${API_BASE}/documents/fix`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data?.detail
            ? typeof data.detail === "string"
              ? data.detail
              : JSON.stringify(data.detail)
            : `Formatting failed with status ${response.status}.`
        );
      }

      const normalized = normalizeFixResponse(data);
      setFixResult(data);

      if (!normalized.formattingSucceeded) {
        setError(
          "We couldn't safely finish formatting this document. Your original document has not been changed."
        );
      }
    } catch (requestError) {
      setError(
        requestError instanceof AuthSessionError
          ? requestError.message
          : requestError.message ||
              "We could not format this document. Please try again."
      );
      setActiveTab("upload");
    } finally {
      setLoadingAction("");
    }
  };

  const getDownloadUrl = () => {
    if (!fixModel?.formattingSucceeded || !fixModel?.downloadUrl) {
      return null;
    }

    if (
      fixModel.downloadUrl.startsWith("http://") ||
      fixModel.downloadUrl.startsWith("https://")
    ) {
      return fixModel.downloadUrl;
    }

    return `${API_BASE}${fixModel.downloadUrl}`;
  };

  const downloadUrl = getDownloadUrl();

  const handleDownload = async () => {
    if (!downloadUrl) {
      return;
    }

    try {
      setError("");
      await downloadAuthenticatedFile(
        downloadUrl,
        "formatted.docx"
      );
    } catch (requestError) {
      setError(
        requestError instanceof AuthSessionError
          ? requestError.message
          : requestError.message ||
              "We could not download the formatted document. Please try again."
      );
    }
  };

  return (
    <div className="formatterShell">
      {!hasWorkspaceContent && (
        <HeroSection onFormatClick={scrollToWorkspace} />
      )}

      <section
        id="workspace"
        className="workspaceSection"
        ref={workspaceRef}
        aria-labelledby="workspace-heading"
      >
        <div className="workspaceHeader">
          <div>
            <h2 id="workspace-heading">Prepare your document</h2>
            <p>
              Add your content and choose how the paper should be structured.
            </p>
          </div>

          <span className="templateBadge">APA 7 Student Paper</span>
        </div>

        <div className="workspaceGrid">
          <PaperSetupPanel
            templateId={templateId}
            templateOptions={TEMPLATE_OPTIONS}
            onTemplateChange={handleTemplateChange}
            isLoading={isLoading}
            onAnalyze={handleAnalyze}
            onFix={handleFix}
            onAnalyzeAgain={handleAnalyze}
            file={file}
            analyzeResult={analyzeResult}
            fixResult={fixResult}
            safeCount={safeCount}
            canFix={Boolean(analysis?.canFix)}
            loadingAction={loadingAction}
          />

          <DocumentInputPanel
            activeTab={activeTab}
            onTabChange={setActiveTab}
            fileInputRef={fileInputRef}
            file={file}
            isDragging={isDragging}
            isLoading={isLoading}
            error={error}
            loadingAction={loadingAction}
            analyzeResult={analyzeResult}
            analysis={analysis}
            fixResult={fixResult}
            fixModel={fixModel}
            scoreLabel={scoreLabel}
            scoreTone={scoreTone}
            visibleFixedCounts={visibleFixedCounts}
            totalFixed={totalFixed}
            downloadUrl={downloadUrl}
            onDownload={handleDownload}
            formatFileSize={formatFileSize}
            onFileChange={handleFileChange}
            onDrop={handleDrop}
            onDragEnter={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onBrowse={() => fileInputRef.current?.click()}
            onResetWorkflow={resetWorkflow}
            onFix={handleFix}
            onAnalyzeAgain={handleAnalyze}
          />
        </div>
      </section>

      <HowItWorks />
    </div>
  );
}

export default FormatterApp;
