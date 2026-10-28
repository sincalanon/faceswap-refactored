// Faceswap 简易版 Windows 启动器：使用同目录下的便携 Python 启动 app.py（中文网页界面）
using System;
using System.Diagnostics;
using System.IO;
using System.Text;

internal static class Launcher
{
    private static int Fail(string message)
    {
        Console.WriteLine(message);
        Console.WriteLine("按任意键退出...");
        try { Console.ReadKey(true); } catch (InvalidOperationException) { }
        return 1;
    }

    private static string Quote(string arg)
    {
        return "\"" + arg.Replace("\"", "\\\"") + "\"";
    }

    private static int Main(string[] args)
    {
        try { Console.OutputEncoding = Encoding.UTF8; } catch (IOException) { }
        Console.Title = "Faceswap 简易版（关闭此窗口即退出）";
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.Combine(root, "python", "python.exe");
        string source = Path.Combine(root, "faceswap");
        string app = Path.Combine(source, "app.py");
        if (!File.Exists(python) || !File.Exists(app))
        {
            return Fail("找不到内置的 Python 或程序文件。请完整解压整个压缩包后，再运行 FaceswapSimple.exe。");
        }

        var arguments = new StringBuilder("-u " + Quote(app));
        bool hasBrowserFlag = false;
        foreach (string arg in args)
        {
            if (arg == "--no-browser") { hasBrowserFlag = true; continue; }
            arguments.Append(' ').Append(Quote(arg));
        }
        if (!hasBrowserFlag) { arguments.Append(" --inbrowser"); }

        var info = new ProcessStartInfo(python, arguments.ToString())
        {
            UseShellExecute = false,
            WorkingDirectory = source,
        };
        info.EnvironmentVariables["FACESWAP_BACKEND"] = "nvidia";
        info.EnvironmentVariables["KERAS_BACKEND"] = "torch";
        info.EnvironmentVariables["PYTHONUTF8"] = "1";
        info.EnvironmentVariables["PYTHONNOUSERSITE"] = "1";
        info.EnvironmentVariables["GRADIO_ANALYTICS_ENABLED"] = "False";
        info.EnvironmentVariables.Remove("PYTHONHOME");
        info.EnvironmentVariables.Remove("PYTHONPATH");

        Console.WriteLine("正在启动 Faceswap 简易版，首次启动可能需要一两分钟……");
        Console.WriteLine("浏览器会自动打开 http://127.0.0.1:7860 ，使用期间请不要关闭本窗口。");
        Console.WriteLine();
        using (Process process = Process.Start(info))
        {
            process.WaitForExit();
            if (process.ExitCode != 0)
            {
                return Fail("程序异常退出（代码 " + process.ExitCode + "），请查看上方日志。");
            }
            return 0;
        }
    }
}
