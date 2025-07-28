import React from "react";
import TeamsTable from "./components/TeamsTable";

const App = () => {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">NBA Teams</h1>
      <TeamsTable />
    </div>
  );
};

export default App;
