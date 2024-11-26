/*
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2023-2024 Vypercore. All Rights Reserved
 */

import JobDashboard from "@/features/JobDashboard";
import { useRoutes } from "react-router-dom";

export const AppRoutes = () => {
    const element = useRoutes([{ path: "*", element: <JobDashboard /> }]);
    return <>{element}</>;
};
