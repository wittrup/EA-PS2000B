program EAPS2000B;

uses
  Vcl.Forms,
  uMFrm in 'uMFrm.pas' {Form1},
  PS2000_struct in 'PS2000_struct.pas',
  bfRec in 'bfRec.pas';

{$R *.res}

begin
  Application.Initialize;
  Application.MainFormOnTaskbar := True;
  Application.CreateForm(TForm1, Form1);
  Application.Run;
end.
