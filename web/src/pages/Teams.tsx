import { useEffect, useState } from "react";

type Team = {
  id: number;
  full_name: string;
  abbreviation: string;
  nickname: string;
  city: string;
  state: string;
  year_founded: int;
};

export default function Teams() {
  const [teams, setTeams] = useState<Team[]>([]);

  useEffect(() => {
    fetch("http://localhost:8000/api/v1/teams/")
      .then((res) => res.json())
      .then((data) => setTeams(data));
  }, []);

  return (
    <div className="p-4">
      <h1 className="text-xl font-bold mb-4">Teams</h1>
      <table className="table-auto w-full border border-gray-200">
        <thead>
          <tr>
            <th className="px-4 py-2">Name</th>
            <th className="px-4 py-2">Abbreviation</th>
            <th className="px-4 py-2">Nickname</th>
            <th className="px-4 py-2">City</th>
            <th className="px-4 py-2">State</th>
            <th className="px-4 py-2">Year Founded</th>
          </tr>
        </thead>
        <tbody>
          {teams.map((team) => (
            <tr key={team.id}>
              <td className="border px-4 py-2">{team.full_name}</td>
              <td className="border px-4 py-2">{team.abbreviation}</td>
              <td className="border px-4 py-2">{team.nickname}</td>
              <td className="border px-4 py-2">{team.city}</td>
              <td className="border px-4 py-2">{team.state}</td>
              <td className="border px-4 py-2">{team.year_founded}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
