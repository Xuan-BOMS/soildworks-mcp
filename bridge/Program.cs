using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Threading;
using Microsoft.Win32;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

internal static class Program
{
    [DllImport("ole32.dll", CharSet = CharSet.Unicode)]
    private static extern int CLSIDFromProgID(string progId, out Guid clsid);

    [DllImport("oleaut32.dll", PreserveSig = false)]
    private static extern void GetActiveObject(ref Guid rclsid, IntPtr reserved, [MarshalAs(UnmanagedType.IUnknown)] out object? ppunk);

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = false,
    };
    private const string SolidWorksProgId = "SldWorks.Application";
    private static readonly TimeSpan LaunchTimeout = TimeSpan.FromSeconds(60);
    private static readonly TimeSpan LaunchPollInterval = TimeSpan.FromMilliseconds(500);

    private static SldWorks? CachedApp;

    private static readonly Dictionary<string, string[]> PlaneAliases = new(StringComparer.OrdinalIgnoreCase)
    {
        ["front"] = ["Front Plane", "前视基准面"],
        ["top"] = ["Top Plane", "上视基准面"],
        ["right"] = ["Right Plane", "右视基准面"],
    };

    [STAThread]
    public static int Main(string[] args)
    {
        try
        {
            if (args.Length == 0)
            {
                WriteError("missing_command", "Bridge command is required.");
                return 1;
            }

            if (string.Equals(args[0], "serve", StringComparison.OrdinalIgnoreCase))
            {
                return Serve();
            }

            string payloadJson = args.Length > 1
                ? (args[1] == "-" ? Console.In.ReadToEnd() : args[1])
                : "{}";
            payloadJson = payloadJson.TrimStart('\uFEFF', '\u200B', '\r', '\n', ' ', '\t');
            using JsonDocument payload = JsonDocument.Parse(payloadJson);
            object result = ExecuteCommand(args[0], payload.RootElement);

            Console.WriteLine(JsonSerializer.Serialize(result, JsonOptions));
            return 0;
        }
        catch (Exception ex)
        {
            WriteError("bridge_exception", ex.ToString());
            return 1;
        }
    }

    private static int Serve()
    {
        string? line;
        while ((line = Console.ReadLine()) != null)
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            try
            {
                using JsonDocument request = JsonDocument.Parse(line);
                string command = request.RootElement.GetProperty("command").GetString()
                    ?? throw new InvalidOperationException("Request command is required.");
                string payloadJson = request.RootElement.TryGetProperty("payload", out JsonElement payloadElement)
                    ? payloadElement.GetRawText()
                    : "{}";
                using JsonDocument payload = JsonDocument.Parse(payloadJson);
                object result = ExecuteCommand(command, payload.RootElement);
                Console.WriteLine(JsonSerializer.Serialize(result, JsonOptions));
            }
            catch (Exception ex)
            {
                WriteError("bridge_exception", ex.ToString());
            }
        }

        return 0;
    }

    private static object ExecuteCommand(string command, JsonElement payload)
    {
        return command switch
        {
            "ping" => new { ok = true, bridge = "solidworks-bridge" },
            "new_part" => NewPart(payload),
            "create_sketch_on_plane" => CreateSketchOnPlane(payload),
            "create_center_rectangle" => CreateCenterRectangle(payload),
            "create_circle" => CreateCircle(payload),
            "add_dimension" => AddDimension(payload),
            "extrude_boss" => ExtrudeBoss(payload),
            "run_macro" => RunMacro(payload),
            _ => throw new InvalidOperationException($"Unknown command: {command}")
        };
    }

    private static object NewPart(JsonElement payload)
    {
        var app = AttachOrLaunch(true, ensureVisible: false);
        string templatePath = payload.TryGetProperty("templatePath", out JsonElement templateElement)
            ? templateElement.GetString() ?? string.Empty
            : @"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2023\templates\gb_part.prtdot";

        if (!File.Exists(templatePath))
        {
            return new { ok = false, reason = "template_not_found", templatePath };
        }

        ModelDoc2? doc = app.NewDocument(templatePath, 0, 0.0, 0.0) as ModelDoc2;
        ModelDoc2? active = app.ActiveDoc as ModelDoc2;
        return new
        {
            ok = doc != null && active != null,
            templatePath,
            activeTitle = active?.GetTitle(),
        };
    }

    private static object CreateSketchOnPlane(JsonElement payload)
    {
        var app = AttachOrLaunch(false, ensureVisible: false);
        ModelDoc2 model = RequireActiveModel(app);
        ModelDocExtension ext = model.Extension;
        string plane = payload.TryGetProperty("plane", out JsonElement planeElement)
            ? planeElement.GetString() ?? "front"
            : "front";
        string planeKey = NormalizePlaneKey(plane);

        string[] candidateNames = PlaneAliases.TryGetValue(planeKey, out string[]? aliases)
            ? aliases
            : [plane];

        bool selected = false;
        string? selectedName = null;
        foreach (string name in candidateNames)
        {
            selected = ext.SelectByID2(name, "PLANE", 0, 0, 0, false, 0, null, 0);
            if (selected)
            {
                selectedName = name;
                break;
            }
        }

        if (!selected)
        {
            return new { ok = false, reason = "plane_not_found", plane };
        }

        model.SketchManager.InsertSketch(true);
        return new
        {
            ok = true,
            plane = plane,
            selectedName,
            hasActiveSketch = GetActiveSketch(model) != null,
        };
    }

    private static object CreateCircle(JsonElement payload)
    {
        var app = AttachOrLaunch(false, ensureVisible: false);
        ModelDoc2 model = RequireActiveModel(app);
        SketchManager sketchManager = model.SketchManager;

        double centerX = payload.GetProperty("centerX").GetDouble();
        double centerY = payload.GetProperty("centerY").GetDouble();
        double centerZ = payload.TryGetProperty("centerZ", out JsonElement centerZElement) ? centerZElement.GetDouble() : 0.0;
        double radius = payload.GetProperty("radius").GetDouble();

        object? circle = sketchManager.CreateCircleByRadius(centerX, centerY, centerZ, radius);
        SketchSegment[] activeSegments = GetActiveSketchSegments(model);
        return new
        {
            ok = circle != null,
            radius,
            activeSketchSegmentCount = activeSegments.Length,
        };
    }

    private static object CreateCenterRectangle(JsonElement payload)
    {
        var app = AttachOrLaunch(false, ensureVisible: false);
        ModelDoc2 model = RequireActiveModel(app);
        SketchManager sketchManager = model.SketchManager;

        double centerX = payload.GetProperty("centerX").GetDouble();
        double centerY = payload.GetProperty("centerY").GetDouble();
        double centerZ = payload.TryGetProperty("centerZ", out JsonElement centerZElement) ? centerZElement.GetDouble() : 0.0;
        double cornerX = payload.GetProperty("cornerX").GetDouble();
        double cornerY = payload.GetProperty("cornerY").GetDouble();
        double cornerZ = payload.TryGetProperty("cornerZ", out JsonElement cornerZElement) ? cornerZElement.GetDouble() : 0.0;

        object?[]? segments = sketchManager.CreateCenterRectangle(centerX, centerY, centerZ, cornerX, cornerY, cornerZ) as object[];
        SketchSegment[] activeSegments = GetActiveSketchSegments(model);
        return new
        {
            ok = segments != null,
            segmentCount = segments?.Length ?? 0,
            activeSketchSegmentCount = activeSegments.Length,
        };
    }

    private static object AddDimension(JsonElement payload)
    {
        string method = payload.TryGetProperty("method", out JsonElement methodElement)
            ? methodElement.GetString() ?? "macro"
            : "macro";

        if (string.Equals(method, "macro", StringComparison.OrdinalIgnoreCase) || string.Equals(method, "safe", StringComparison.OrdinalIgnoreCase))
        {
            return new
            {
                ok = false,
                reason = "macro_method_unavailable_on_host",
                method,
                detail = "The VSTA macro entry required for in-process dimensioning is not stable on this host. Use high-level modeling tools or direct mode only for diagnosis.",
            };
        }

        if (string.Equals(method, "direct", StringComparison.OrdinalIgnoreCase))
        {
            return new
            {
                ok = false,
                reason = "direct_method_disabled",
                method,
                recommendedMethod = "create_rectangular_block|create_plate_with_holes|design_from_prompt",
                detail = "Direct out-of-proc dimension creation is disabled because it can hang or crash SolidWorks on this host.",
            };
        }

        return new
        {
            ok = false,
            reason = "unsupported_dimension_method",
            method,
            recommendedMethod = "create_rectangular_block|create_plate_with_holes|design_from_prompt",
            detail = "Dimension methods are currently disabled on this host because stable in-process automation is unavailable.",
        };
    }

    private static object ExtrudeBoss(JsonElement payload)
    {
        var app = AttachOrLaunch(false, ensureVisible: false);
        ModelDoc2 model = RequireActiveModel(app);
        if (GetActiveSketch(model) != null)
        {
            model.SketchManager.InsertSketch(true);
        }

        model.ClearSelection2(true);
        string? sketchFeatureName = FindLastSketchFeatureName(model);
        if (!string.IsNullOrWhiteSpace(sketchFeatureName))
        {
            model.Extension.SelectByID2(sketchFeatureName, "SKETCH", 0, 0, 0, false, 0, null, 0);
        }

        double depth = payload.GetProperty("depth").GetDouble();
        FeatureManager featureManager = model.FeatureManager;
        Feature? feature = featureManager.FeatureExtrusion3(
            true,
            false,
            false,
            (int)swEndConditions_e.swEndCondBlind,
            (int)swEndConditions_e.swEndCondBlind,
            depth,
            0.0,
            false,
            false,
            false,
            false,
            0.0,
            0.0,
            false,
            false,
            false,
            false,
            true,
            true,
            true,
            0,
            0,
            false
        ) as Feature;

        return new
        {
            ok = feature != null,
            featureName = feature?.Name,
            depth,
            sketchFeatureName,
        };
    }

    private static object RunMacro(JsonElement payload)
    {
        return new
        {
            ok = false,
            reason = "run_macro_disabled_on_host",
            recommendedMethod = "create_rectangular_block|create_plate_with_holes|design_from_prompt",
            detail = "SolidWorks macro execution is disabled on this host because the .NET/VSTA macro loader can raise a Microsoft .NET Framework dialog and terminate SolidWorks.",
        };
    }

    private static SldWorks AttachOrLaunch(bool create, bool ensureVisible)
    {
        SldWorks? app = GetCachedApplication();
        if (app != null)
        {
            if (ensureVisible)
            {
                app.Visible = true;
            }
            app.UserControl = true;
            return app;
        }

        app = TryGetActiveApplication();
        if (app == null)
        {
            if (!create)
            {
                throw new InvalidOperationException("No running SolidWorks instance was found.");
            }
            app = LaunchAndAttachDesktopSolidWorks();
        }

        if (ensureVisible)
        {
            app.Visible = true;
        }
        app.UserControl = true;
        CachedApp = app;
        return app;
    }

    private static SldWorks LaunchAndAttachDesktopSolidWorks()
    {
        string executablePath = ResolveSolidWorksExecutablePath();
        if (!File.Exists(executablePath))
        {
            throw new InvalidOperationException($"SolidWorks executable was not found: {executablePath}");
        }

        var startInfo = new ProcessStartInfo(executablePath)
        {
            UseShellExecute = true,
            WorkingDirectory = Path.GetDirectoryName(executablePath) ?? System.Environment.CurrentDirectory,
        };
        Process.Start(startInfo);

        DateTime deadline = DateTime.UtcNow + LaunchTimeout;
        while (DateTime.UtcNow < deadline)
        {
            SldWorks? app = TryGetActiveApplication();
            if (app != null)
            {
                return app;
            }

            Thread.Sleep(LaunchPollInterval);
        }

        throw new InvalidOperationException("Timed out waiting for SolidWorks to register its COM automation object.");
    }

    private static string ResolveSolidWorksExecutablePath()
    {
        using RegistryKey? progIdKey = Registry.ClassesRoot.OpenSubKey($"{SolidWorksProgId}\\CLSID");
        string? clsid = progIdKey?.GetValue(null) as string;
        if (string.IsNullOrWhiteSpace(clsid))
        {
            throw new InvalidOperationException("SolidWorks CLSID registry entry was not found.");
        }

        using RegistryKey? serverKey = Registry.ClassesRoot.OpenSubKey($@"CLSID\{clsid}\LocalServer32");
        string? localServer = serverKey?.GetValue(null) as string;
        if (string.IsNullOrWhiteSpace(localServer))
        {
            throw new InvalidOperationException("SolidWorks LocalServer32 registry entry was not found.");
        }

        string trimmed = localServer.Trim();
        if (trimmed.StartsWith('"'))
        {
            int endQuote = trimmed.IndexOf('"', 1);
            if (endQuote > 1)
            {
                return trimmed.Substring(1, endQuote - 1);
            }
        }

        int exeIndex = trimmed.IndexOf(".exe", StringComparison.OrdinalIgnoreCase);
        if (exeIndex >= 0)
        {
            return trimmed.Substring(0, exeIndex + 4);
        }

        return trimmed;
    }

    private static SldWorks? GetCachedApplication()
    {
        if (CachedApp == null)
        {
            return null;
        }

        try
        {
            _ = CachedApp.Visible;
            return CachedApp;
        }
        catch (COMException)
        {
            CachedApp = null;
            return null;
        }
    }

    private static SldWorks? TryGetActiveApplication()
    {
        int hr = CLSIDFromProgID(SolidWorksProgId, out Guid clsid);
        if (hr < 0)
        {
            Marshal.ThrowExceptionForHR(hr);
        }

        try
        {
            GetActiveObject(ref clsid, IntPtr.Zero, out object? instance);
            return instance as SldWorks;
        }
        catch (COMException ex) when ((uint)ex.HResult == 0x800401E3)
        {
            return null;
        }
    }

    private static ModelDoc2 RequireActiveModel(SldWorks app)
    {
        return app.ActiveDoc as ModelDoc2 ?? throw new InvalidOperationException("No active SolidWorks document.");
    }

    private static Sketch? GetActiveSketch(ModelDoc2 model)
    {
        return model.GetActiveSketch2() as Sketch;
    }

    private static string? FindLastSketchFeatureName(ModelDoc2 model)
    {
        return FindLastSketchFeature(model)?.Name;
    }

    private static Feature? FindLastSketchFeature(ModelDoc2 model)
    {
        Feature? feature = model.FirstFeature() as Feature;
        Feature? lastSketchFeature = null;
        while (feature != null)
        {
            string typeName = feature.GetTypeName2();
            if (string.Equals(typeName, "ProfileFeature", StringComparison.OrdinalIgnoreCase))
            {
                lastSketchFeature = feature;
            }

            feature = feature.GetNextFeature() as Feature;
        }

        return lastSketchFeature;
    }

    private static SketchSegment[] GetActiveSketchSegments(ModelDoc2 model)
    {
        Sketch? sketch = GetActiveSketch(model);
        if (sketch == null)
        {
            return Array.Empty<SketchSegment>();
        }

        object[] segments = (sketch.GetSketchSegments() as object[]) ?? Array.Empty<object>();
        return segments.OfType<SketchSegment>().ToArray();
    }

    private static SketchSegment[] GetEditableSketchSegments(ModelDoc2 model)
    {
        SketchSegment[] activeSegments = GetActiveSketchSegments(model);
        if (activeSegments.Length > 0)
        {
            return activeSegments;
        }

        Feature? sketchFeature = FindLastSketchFeature(model);
        if (sketchFeature == null)
        {
            return Array.Empty<SketchSegment>();
        }

        model.ClearSelection2(true);
        bool selected = model.Extension.SelectByID2(sketchFeature.Name, "SKETCH", 0, 0, 0, false, 0, null, 0);
        if (!selected)
        {
            return Array.Empty<SketchSegment>();
        }

        model.EditSketch();
        return GetActiveSketchSegments(model);
    }

    private static bool IsHorizontalSegment(SketchSegment segment)
    {
        if (segment is not SketchLine line)
        {
            return false;
        }

        SketchPoint startPoint = (SketchPoint)line.GetStartPoint2();
        SketchPoint endPoint = (SketchPoint)line.GetEndPoint2();
        return Math.Abs(startPoint.Y - endPoint.Y) < 1e-9;
    }

    private static bool IsVerticalSegment(SketchSegment segment)
    {
        if (segment is not SketchLine line)
        {
            return false;
        }

        SketchPoint startPoint = (SketchPoint)line.GetStartPoint2();
        SketchPoint endPoint = (SketchPoint)line.GetEndPoint2();
        return Math.Abs(startPoint.X - endPoint.X) < 1e-9;
    }

    private static void WriteError(string code, string detail)
    {
        Console.WriteLine(JsonSerializer.Serialize(new { ok = false, errorCode = code, detail }, JsonOptions));
    }

    private static string NormalizePlaneKey(string plane)
    {
        if (string.IsNullOrWhiteSpace(plane))
        {
            return "front";
        }

        string normalized = plane.Trim().ToLowerInvariant();
        if (normalized.Contains("front"))
        {
            return "front";
        }

        if (normalized.Contains("top"))
        {
            return "top";
        }

        if (normalized.Contains("right"))
        {
            return "right";
        }

        return normalized;
    }
}
