import React, { useEffect, useState } from "react";

type Team = {
  id: string;
  full_name: string;
  abbreviation: string;
  nickname: string;
  city: string;
  state: string;
  year_founded: string;
};

const TeamsTable = () => {
  const [teams, setTeams] = useState<Team[]>([]);

  useEffect(() => {
    fetch("http://localhost:8000/api/v1/teams/") // adjust this if behind a proxy
      .then((res) => res.json())
      .then((data) => setTeams(data));
  }, []);

  return (
    <div className="overflow-x-auto">
      <table className="table-auto w-full text-left bg-white shadow-md rounded-lg">
        <thead className="bg-gray-100">
          <tr>
            <th className="px-4 py-2">Team</th>
            <th className="px-4 py-2">Abbreviation</th>
            <th className="px-4 py-2">Nickname</th>
            <th className="px-4 py-2">City</th>
            <th className="px-4 py-2">State</th>
            <th className="px-4 py-2">Year Founded</th>
          </tr>
        </thead>
        <tbody>
          {teams.map((team) => (
            <tr key={team.id} className="border-t">
              <td className="px-4 py-2">{team.full_name}</td>
              <td className="px-4 py-2">{team.abbreviation}</td>
              <td className="px-4 py-2">{team.nickname}</td>
              <td className="px-4 py-2">{team.city}</td>
              <td className="px-4 py-2">{team.state}</td>
              <td className="px-4 py-2">{team.year_founded}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default TeamsTable;
