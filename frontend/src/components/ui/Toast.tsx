import toast, { Toaster as HotToaster } from "react-hot-toast";
import { CheckCircle, XCircle, AlertTriangle, Info } from "lucide-react";

export function Toaster() {
  return (
    <HotToaster
      position="top-right"
      toastOptions={{
        duration: 4000,
        style: {
          background: "rgba(15, 23, 42, 0.95)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(255, 255, 255, 0.1)",
          color: "#fff",
          borderRadius: "16px",
          padding: "14px 18px",
          fontSize: "14px",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.4)",
        },
      }}
    />
  );
}

export function showSuccess(message: string) {
  toast(message, {
    icon: <CheckCircle className="w-5 h-5 text-emerald-400 flex-shrink-0" />,
    style: {
      background: "rgba(15, 23, 42, 0.95)",
      backdropFilter: "blur(20px)",
      border: "1px solid rgba(16, 185, 129, 0.2)",
      color: "#fff",
      borderRadius: "16px",
      padding: "14px 18px",
      fontSize: "14px",
      boxShadow: "0 20px 40px rgba(0, 0, 0, 0.4)",
    },
  });
}

export function showError(message: string) {
  toast(message, {
    icon: <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />,
    duration: 5000,
    style: {
      background: "rgba(15, 23, 42, 0.95)",
      backdropFilter: "blur(20px)",
      border: "1px solid rgba(239, 68, 68, 0.2)",
      color: "#fff",
      borderRadius: "16px",
      padding: "14px 18px",
      fontSize: "14px",
      boxShadow: "0 20px 40px rgba(0, 0, 0, 0.4)",
    },
  });
}

export function showWarning(message: string) {
  toast(message, {
    icon: <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />,
    style: {
      background: "rgba(15, 23, 42, 0.95)",
      backdropFilter: "blur(20px)",
      border: "1px solid rgba(245, 158, 11, 0.2)",
      color: "#fff",
      borderRadius: "16px",
      padding: "14px 18px",
      fontSize: "14px",
      boxShadow: "0 20px 40px rgba(0, 0, 0, 0.4)",
    },
  });
}

export function showInfo(message: string) {
  toast(message, {
    icon: <Info className="w-5 h-5 text-blue-400 flex-shrink-0" />,
    style: {
      background: "rgba(15, 23, 42, 0.95)",
      backdropFilter: "blur(20px)",
      border: "1px solid rgba(59, 130, 246, 0.2)",
      color: "#fff",
      borderRadius: "16px",
      padding: "14px 18px",
      fontSize: "14px",
      boxShadow: "0 20px 40px rgba(0, 0, 0, 0.4)",
    },
  });
}
