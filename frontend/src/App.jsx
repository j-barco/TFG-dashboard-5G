import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import Topology from "./pages/Topology";
import GnbConfig from "./pages/GnbConfig";
import CoreServices from "./pages/CoreServices";
import Subscribers from "./pages/Subscribers";

function Protected({ children }) {
  return (
    <ProtectedRoute>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <Protected>
                <Overview />
              </Protected>
            }
          />
          <Route
            path="/topologia"
            element={
              <Protected>
                <Topology />
              </Protected>
            }
          />
          <Route
            path="/gnb"
            element={
              <Protected>
                <GnbConfig />
              </Protected>
            }
          />
          <Route
            path="/nucleo"
            element={
              <Protected>
                <CoreServices />
              </Protected>
            }
          />
          <Route
            path="/suscriptores"
            element={
              <Protected>
                <Subscribers />
              </Protected>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
